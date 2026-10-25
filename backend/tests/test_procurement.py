"""Isolated synthetic shopping fixtures; no online calls or real merchant quotes."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import procurement
from app.decision import decide
from app.hardware_models import DialogueRequest, HardwareProject
from app.main import app
from app.planning import BuildPlan, PurchaseSpec


def plan_fixture():
    return {'title':'合成测试小车方案','summary':'仅用于离线结构验收','selected_route':'合成两轮小车路线',
            'selection_reason':'测试数量、完整性与来源处理，不代表真实硬件建议。','options':[],
            'purchase_items':[{'id':'wheels','name':'合成65mm轮子','category':'机械','kind':'mechanical','quantity':2,'unit':'个',
              'specs':'测试用65mm TT轴孔','purpose':'测试移动机构','selection_reason':'隔离夹具',
              'compatibility_checks':['核对轴孔和SKU包装数量'],'search_query':'65mm TT轮子','match_terms':['65mm','TT']}],
            'coverage':[{'function':'移动','item_ids':['wheels'],'note':'合成夹具'}],
            'assembly_steps':['测试步骤，未进行实际装配'],'acceptance_checks':['检查合成数量为2'],'unresolved':[]}


def conversation_fixture():
    return {'project':HardwareProject(conversation_id='11111111-1111-4111-8111-111111111111').model_dump(mode='json'),
            'decision_trace':{'id':'22222222-2222-4222-8222-222222222222'},'build_plan':plan_fixture()}


def hit(url='https://item.jd.com/123456.html',title='65mm TT轮子 合成夹具',snippet='仅测试数据，不是商家真实报价'):
    return {'id':'synthetic-1','title':title,'url':url,'snippet':snippet}


def test_plan_coverage_and_duplicate_ids_must_be_valid():
    plan=plan_fixture();plan['coverage'][0]['item_ids']=['missing']
    with pytest.raises(ValueError):BuildPlan.model_validate(plan)
    plan=plan_fixture();plan['purchase_items'].append(copy.deepcopy(plan['purchase_items'][0]))
    with pytest.raises(ValueError):BuildPlan.model_validate(plan)


def test_product_link_requires_relevant_terms_and_actual_detail_url():
    item=BuildPlan.model_validate(plan_fixture()).purchase_items[0]
    products=procurement.select_products(item,[hit(),hit('https://search.jd.com/Search?keyword=wheel'),hit('https://item.jd.com/999.html','Arduino控制板','合成错误类别')])
    assert len(products)==1 and products[0]['match_status']=='text_matches_requested_terms'
    assert products[0]['sku_verified'] is False and products[0]['unit_price_cny'] is None


def test_starting_sku_tier_and_foreign_price_are_not_accepted_as_unit_price():
    item=BuildPlan.model_validate(plan_fixture()).purchase_items[0]
    for quote in ('¥5起','¥5 或 ¥15，不同套装','JPY ¥500'):
        assert procurement.select_products(item,[hit(snippet=quote)])[0]['unit_price_cny'] is None


@pytest.mark.asyncio
async def test_owned_items_make_no_searches_and_missing_detail_is_honest():
    item=BuildPlan.model_validate(plan_fixture()).purchase_items[0]
    calls=[]
    async def searcher(mode,queries,sites=None):
        calls.append((mode,queries,sites))
        return {'status':'ok','request_count':1,'request_ids':['synthetic-request'],'results':[hit('https://example.invalid/reference')],'error':None}
    item.owned=True
    owned=await procurement.source_item(item,searcher)
    assert owned['status']=='owned' and not calls
    item.owned=False
    unknown=await procurement.source_item(item,searcher)
    assert unknown['status']=='needs_product_link' and not unknown['products']
    assert len(calls)==3 and all(call[0]=='live' for call in calls)


@pytest.mark.asyncio
async def test_searches_taobao_tmall_and_jd_independently_even_when_jd_has_a_hit():
    item=BuildPlan.model_validate(plan_fixture()).purchase_items[0]
    calls=[]
    channel_hits={
        'taobao.com':hit('https://item.taobao.com/item.htm?id=111','65mm TT轮子 淘宝商品','65mm TT轮子；价格以商品页为准'),
        'tmall.com':hit('https://detail.tmall.com/item.htm?id=222','65mm TT轮子 天猫商品','65mm TT轮子；价格以商品页为准'),
        'jd.com':hit(),
    }
    async def searcher(mode,queries,sites=None):
        calls.append((mode,queries,sites))
        lead=channel_hits[sites[0]]
        return {'status':'ok','request_count':1,'request_ids':[sites[0]],'results':[lead],'error':None}
    result=await procurement.source_item(item,searcher)
    assert [call[2][0] for call in calls]==['taobao.com','tmall.com','jd.com']
    assert [product['platform'] for product in result['products']]==['淘宝','天猫','京东']
    assert [channel['status'] for channel in result['channel_searches']]==['found','found','found']
    assert all(product['unit_price_cny'] is None and product['sku_verified'] is False for product in result['products'])
    assert all(procurement.product_link(row['url'])['platform'] in ('淘宝','天猫','京东') for row in result['references'])


def test_required_terms_are_not_satisfied_by_one_keyword_or_battery_substring():
    item=BuildPlan.model_validate(plan_fixture()).purchase_items[0]
    assert not procurement.select_products(item,[hit(title='65mm其他轮子',snippet='没有目标轴孔')])
    assert not procurement.term_matches('TT','battery charger')
    assert procurement.term_matches('5路','TCRT5000 5-Channel sensor')


@pytest.mark.asyncio
async def test_job_progress_idempotency_and_bom_are_consistent(tmp_path,monkeypatch):
    monkeypatch.setattr(procurement,'ROOT',tmp_path)
    async def searcher(mode,queries,sites=None):
        urls={'taobao.com':'https://item.taobao.com/item.htm?id=111','tmall.com':'https://detail.tmall.com/item.htm?id=222','jd.com':'https://item.jd.com/123456.html'}
        return {'status':'ok','request_count':1,'request_ids':['synthetic-request'],'results':[hit(urls[sites[0]])],'error':None}
    conversation=conversation_fixture()
    job,created=procurement.create_job(conversation)
    assert created and procurement.create_job(conversation)[1] is False
    finished=await procurement.run_job(job['id'],searcher)
    assert finished['status']=='complete' and finished['completed_items']==1
    assert finished['search_request_count']==3 and finished['budget']['total_cny'] is None
    assert [p['platform'] for p in finished['items'][0]['products']]==['淘宝','天猫','京东']
    project,count=procurement.apply_to_project(finished,HardwareProject.model_validate(conversation['project']))
    assert count==1 and project.bom[0].quantity==2 and project.custom_parts[0].facts=={}
    assert project.bom[0].unit_price_cny is None
    repeated,count=procurement.apply_to_project(finished,project)
    assert not count and len(repeated.bom)==1
    assert procurement.latest_job(project.conversation_id)['id']==job['id']
    procurement.ACTIVE.discard(job['id'])


def test_server_restart_marks_unfinished_job_interrupted(tmp_path,monkeypatch):
    monkeypatch.setattr(procurement,'ROOT',tmp_path)
    job,_=procurement.create_job(conversation_fixture())
    procurement.ACTIVE.discard(job['id'])
    assert procurement.read_job(job['id'])['status']=='interrupted'


def test_old_sourcing_job_is_replaced_for_the_same_decision(tmp_path,monkeypatch):
    monkeypatch.setattr(procurement,'ROOT',tmp_path)
    conversation=conversation_fixture()
    old,_=procurement.create_job(conversation)
    old['sourcing_version']=procurement.SOURCING_VERSION-1
    procurement.save_job(old)

    refreshed,created=procurement.create_job(conversation)

    assert created and refreshed['id']!=old['id']
    assert refreshed['sourcing_version']==procurement.SOURCING_VERSION
    assert procurement.latest_job(conversation['project']['conversation_id'])['id']==refreshed['id']
    procurement.ACTIVE.discard(old['id'])
    procurement.ACTIVE.discard(refreshed['id'])


def test_windows_polling_and_progress_writes_do_not_corrupt_or_lock_job(tmp_path,monkeypatch):
    monkeypatch.setattr(procurement,'ROOT',tmp_path)
    job,_=procurement.create_job(conversation_fixture())
    def writer():
        for revision in range(40):
            job['synthetic_test_revision']=revision;procurement.save_job(job)
    def reader():
        for _ in range(60):assert procurement.read_job(job['id'])['id']==job['id']
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures=[pool.submit(writer),*(pool.submit(reader) for _ in range(4))]
        for future in futures:future.result()
    assert procurement.read_job(job['id'])['synthetic_test_revision']==39
    procurement.ACTIVE.discard(job['id'])


@pytest.mark.asyncio
async def test_semantic_matcher_cannot_invent_urls_or_verify_sku():
    item=BuildPlan.model_validate(plan_fixture()).purchase_items[0]
    row={**item.model_dump(mode='json'),'products':[],'candidate_products':procurement.product_candidates([hit()]),'status':'needs_product_link'}
    actual=row['candidate_products'][0]['candidate_id']
    async def caller(messages):
        return json.dumps({'items':[{'item_id':item.id,'selected_candidate_ids':['invented',actual],'status':'product_lead','reason':'synthetic identity review','checks':['SKU remains unverified']}]}),{'request_id':'synthetic-model'}
    job={'items':[row]}
    await procurement.match_product_identities(job,caller)
    assert len(row['products'])==1 and row['products'][0]['url']==hit()['url']
    assert not row['products'][0]['sku_verified'] and not row['products'][0]['compatibility_verified']


@pytest.mark.asyncio
async def test_resume_retains_completed_rows_without_duplicate_searches(tmp_path,monkeypatch):
    monkeypatch.setattr(procurement,'ROOT',tmp_path)
    job,_=procurement.create_job(conversation_fixture())
    item=BuildPlan.model_validate(job['plan']).purchase_items[0]
    job['items']=[{**item.model_dump(mode='json'),'products':procurement.select_products(item,[hit()]),'searches':[],'position':0,'status':'links_found'}]
    job['completed_items']=1;procurement.save_job(job)
    async def no_search(*args,**kwargs):raise AssertionError('Completed rows must not be searched again')
    result=await procurement.run_job(job['id'],no_search)
    assert result['status']=='complete' and len(result['items'])==1


def test_csv_unknown_parts_have_defaults_and_invalid_rows_leave_no_orphans():
    from app.hardware_service import import_bom
    result=import_bom('ref,mpn,quantity\nU1,synthetic-controller,1\nU2,synthetic-invalid,0')
    assert len(result['custom_parts'])==1 and result['custom_parts'][0]['facts']=={}
    assert 'notes' in result['custom_parts'][0] and len(result['errors'])==1


def test_changed_context_cannot_source_or_apply_old_decision(tmp_path,monkeypatch):
    monkeypatch.setattr(procurement,'ROOT',tmp_path)
    data=conversation_fixture()
    folder=tmp_path/'runtime/conversations';folder.mkdir(parents=True)
    (folder/(data['project']['conversation_id']+'.json')).write_text(json.dumps(data),encoding='utf-8')
    client=TestClient(app)
    response=client.post('/api/hardware/procurement',json={'conversation_id':data['project']['conversation_id'],'decision_id':'33333333-3333-4333-8333-333333333333'})
    assert response.status_code==409
    job,_=procurement.create_job(data)
    procurement.ACTIVE.discard(job['id'])
    data['decision_trace']['id']='33333333-3333-4333-8333-333333333333'
    (folder/(data['project']['conversation_id']+'.json')).write_text(json.dumps(data),encoding='utf-8')
    response=client.post('/api/hardware/procurement/'+job['id']+'/apply',json={'project':data['project']})
    assert response.status_code==409


@pytest.mark.asyncio
async def test_model_cannot_invent_owned_items_and_next_turn_receives_plan(tmp_path,monkeypatch):
    import app.decision as decision
    monkeypatch.setattr(decision,'ROOT',tmp_path)
    plan=plan_fixture();plan['purchase_items'][0].update(owned=True,owned_quote='用户未说过的器材')
    seen=[]
    async def caller(messages):
        seen.append(messages)
        return json.dumps({'assistant_message':'合成决策测试','next_question':None,'build_plan':plan}),{'request_id':'synthetic-model'}
    first=await decide(DialogueRequest(message='我想做小车'),caller=caller)
    assert not first['build_plan']['purchase_items'][0]['owned']
    await decide(DialogueRequest(message='修改预算',project=first['project'],history=first['history']),caller=caller)
    context=json.loads(seen[1][1]['content'])
    assert context['previous_plan']['build_plan']['title']=='合成测试小车方案'
