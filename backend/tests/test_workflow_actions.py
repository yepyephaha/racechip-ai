import json
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.design_runs as design
from app import procurement
from app.discovery import aliases, candidates, normalized
from app.hardware_models import HardwareProject
from test_procurement import plan_fixture


def test_separator_variants_preserve_all_model_digits():
    assert aliases('ESP32S31')==['ESP32S31','ESP32-S31']
    hits=[{'title':'ESP32-S3开发板','url':'https://example.org/other','snippet':'Different device'}, {'title':'ESP32-S31 Datasheet','url':'https://vendor.example/s31','snippet':'Exact requested series'}]
    found=candidates('ESP32S31',hits)
    assert len(found)==1 and found[0]['name']=='ESP32-S31'
    assert found[0]['source_url']=='https://vendor.example/s31'
    assert found[0]['kind']=='unconfirmed'
    assert normalized('土壤 湿度-模块')=='土壤湿度模块'


def test_query_functions_are_not_fabricated_as_exact_part_numbers():
    assert candidates('温湿度无线节点',[{'title':'BME280 sensor','url':'https://example.org','snippet':'example'}])==[]


@pytest.mark.asyncio
async def test_online_search_exposes_results_even_when_local_catalog_has_zero_matches(monkeypatch):
    import app.hardware_api as api
    from app.hardware_models import SearchRequest
    async def search(mode,queries):
        return {'mode':mode,'status':'ok','request_count':2,'request_ids':['fixture-rid'],'results':[{'id':'s1','title':'ESP32-S31 datasheet','url':'https://vendor.example/s31','snippet':'ESP32-S31 specification'}],'error':None}
    monkeypatch.setattr(api,'run_search',search)
    result=await api.search(SearchRequest(query='ESP32S31',mode='live'))
    assert result['local_matches']==[] and len(result['search']['results'])==1
    assert result['discovered_parts'][0]['name']=='ESP32-S31'


def proposal():
    return design.Proposal.model_validate({'message':'隔离测试：生成可审阅草案','assumptions':['建议默认值，不是用户确认'],'next_question':None,'build_plan':plan_fixture(),'links':[]})


def job_for(project):
    return {'id':str(uuid4()),'input':{'project':project.model_dump(mode='json'),'brief':'做一个自动浇水装置，预算目标200元'},'fingerprint':'fixture','created_at':design.now(),'status':'queued','phase':'等待','research':None,'model_calls':[],'answers':[],'proposal':None,'result':None,'procurement_id':None,'error':None}


@pytest.mark.asyncio
async def test_visible_goal_triggers_research_plan_and_sourcing(tmp_path,monkeypatch):
    monkeypatch.setattr(design,'ROOT',tmp_path);monkeypatch.setattr(procurement,'ROOT',tmp_path)
    queries=[];seen=[]
    async def search(mode,items):
        queries.extend(items)
        return {'mode':'live','status':'ok','request_count':2,'request_ids':['synthetic-search'],'results':[],'error':None}
    async def structured(prompt,data,schema,calls,validator,**kwargs):
        seen.append(data);calls.append({'model':'fixture','request_id':'synthetic-model'});p=proposal();validator(p);return p
    async def source(identifier):
        stored=procurement.read_job(identifier);stored.update(status='complete',search_request_count=1,completed_items=1);procurement.save_job(stored);procurement.ACTIVE.discard(identifier)
    monkeypatch.setattr(design,'structured',structured)
    project=HardwareProject(conversation_id=str(uuid4()),name='自动浇水',budget_cny=200,domain='robotics')
    job=job_for(project);design.save(job)
    await design.execute(job['id'],search,source)
    result=design.load(job['id'])
    assert result['status']=='complete' and len(queries)==2
    assert all('自动浇水' in q and 'OpenMV' not in q for q in queries)
    assert seen[0]['current_project']['budget_cny']==200
    assert result['result']['project']['description']==job['input']['brief']
    assert design.public(result)['search_request_count']==3
    assert result['result']['project']['bom']==[]  # Adoption is an explicit visible action.
    applied=await design.apply(job['id'],project)
    assert applied['added_lines']==1 and len(applied['result']['project']['bom'])==1
    again=await design.apply(job['id'],HardwareProject.model_validate(applied['result']['project']))
    assert again['added_lines']==0
    changed=project.model_copy(update={'budget_cny':99})
    with pytest.raises(HTTPException) as error:await design.apply(job['id'],changed)
    assert error.value.status_code==409


@pytest.mark.asyncio
async def test_essential_question_is_visible_without_starting_product_search(tmp_path,monkeypatch):
    monkeypatch.setattr(design,'ROOT',tmp_path)
    async def structured(prompt,data,schema,calls,validator,**kwargs):
        return design.Proposal.model_validate({'message':'需要明确用途','assumptions':[],'next_question':{'key':'fixture','text':'需要几路独立输出？','reason':'会改变执行器数量','choices':['1路','2路']},'build_plan':None,'links':[]})
    monkeypatch.setattr(design,'structured',structured)
    job=job_for(HardwareProject(conversation_id=str(uuid4())))
    job['research']={'status':'ok','request_count':2,'results':[],'error':None}
    design.save(job)
    await design.execute(job['id'])
    result=design.load(job['id'])
    assert result['status']=='needs_input' and result['procurement_id'] is None
    assert result['proposal']['next_question']['choices']==['1路','2路']


@pytest.mark.asyncio
async def test_failed_research_does_not_generate_fake_plan(tmp_path,monkeypatch):
    monkeypatch.setattr(design,'ROOT',tmp_path)
    async def search(mode,items):return {'status':'error','request_count':0,'results':[],'error':'fixture'}
    async def unexpected(*args):raise AssertionError('Model should not run')
    monkeypatch.setattr(design,'structured',unexpected)
    job=job_for(HardwareProject(conversation_id=str(uuid4())));design.save(job)
    await design.execute(job['id'],search)
    result=design.load(job['id'])
    assert result['status']=='error' and result['result'] is None


@pytest.mark.asyncio
async def test_plan_repair_receives_the_specific_schema_message(tmp_path,monkeypatch):
    import app.fact_check as helper
    monkeypatch.setattr(helper,'ROOT',tmp_path)
    bad=proposal().model_dump();bad['build_plan']['purchase_items'][0]['name']='型号A或型号B'
    seen=[]
    async def model(messages,**kwargs):
        seen.append((messages,kwargs))
        return json.dumps(bad if len(seen)==1 else proposal().model_dump(),ensure_ascii=False),{'request_id':'synthetic-json-'+str(len(seen))}
    monkeypatch.setattr(helper,'model_call',model)
    records=[]
    result=await helper.structured('Return JSON',{},design.Proposal,records,use_json_schema=True)
    assert result.build_plan and len(seen)==2
    assert '名称须选定一种规格' in seen[1][0][-1]['content']
    assert seen[0][1]['response_schema']['type']=='object'
