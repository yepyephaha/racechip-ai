import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.decision import model_call, decide, parse_decision, DecisionError
from app.hardware_models import DialogueRequest


def response(**kw):
    obj={"assistant_message":"按你的上下文，我们先比较红外循迹路线。","next_question":{"key":"surface_and_light","text":"路线是在室内固定光照下，还是户外变化光照下？","reason":"光照会影响传感器路线与标定。","choices":["室内固定光照","户外变化光照"]},"confirmed_requirements":[{"key":"tracking_method","value":"红外","source_quote":"我只考虑红外"}],"domain":"robotics","budget_cny":None,"needed_modules":["红外阵列","主控"],"candidate_part_ids":["esp32-devkitc-v4"],"discovered_parts":[],"assumptions":[],"search_queries":[],"change_reason":"依据用户排除了摄像头。"}
    obj.update(kw);return json.dumps(obj,ensure_ascii=False)


@pytest.mark.asyncio
async def test_missing_model_credentials_never_runs_a_fixed_tree():
    with pytest.raises(DecisionError,match="未配置"):
        await model_call([{"role":"user","content":"test"}])
    result=TestClient(app).post('/api/hardware/dialogue',json={'message':'小车循迹'})
    assert result.status_code==503 and result.json()['detail']['fallback_used'] is False


@pytest.mark.asyncio
async def test_context_is_sent_and_question_is_returned_by_api(tmp_path,monkeypatch):
    import app.decision as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    seen=[]
    async def model(messages):
        seen.append(messages)
        return response(),{'provider':'synthetic_model_fixture','model':'fixture','request_id':'fixture-id'}
    request=DialogueRequest(message='我只考虑红外',history=[{'role':'user','text':'预算已经告诉你是600元，室外使用'},{'role':'assistant','text':'之前的方案草案'}])
    result=await decide(request,caller=model)
    assert '室外使用' in seen[0][1]['content']
    assert result['assistant']['question_key']=='surface_and_light'
    assert result['method']=='context_model_api'
    assert result['project']['requirements']['tracking_method']=='红外'
    assert result['decision_trace']['new_model_requests']==1


@pytest.mark.asyncio
async def test_model_can_search_yuanbao_and_redecide(tmp_path,monkeypatch):
    import app.decision as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    calls=[];search_calls=[]
    async def model(messages):
        calls.append(messages)
        return (response(search_queries=['红外循迹 模块 参数']) if len(calls)==1 else response(next_question=None,assistant_message='依据元宝返回，给出待验证模块方案。')),{'request_id':'fixture-'+str(len(calls))}
    async def search(mode,queries):
        search_calls.append((mode,queries));return {'status':'ok','request_count':1,'results':[{'id':'s1','title':'真实来源结构的合成夹具','snippet':'fixture','url':'https://example.invalid'}],'error':None}
    result=await decide(DialogueRequest(message='我只考虑红外'),caller=model,searcher=search)
    assert search_calls==[('live',['红外循迹 模块 参数'])]
    assert len(calls)==2 and 'fixture' in calls[1][-1]['content']
    assert result['ready'] and result['decision_trace']['new_search_requests']==1


@pytest.mark.asyncio
async def test_no_invented_user_constraints_or_unknown_catalog_ids(tmp_path,monkeypatch):
    import app.decision as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    async def model(messages):return response(confirmed_requirements=[{'key':'budget','value':'1元','source_quote':'用户没说过的报价'}],budget_cny=1,candidate_part_ids=['invented-chip']),{'request_id':'fixture'}
    result=await decide(DialogueRequest(message='我只考虑红外'),caller=model)
    assert result['project']['budget_cny'] is None and not result['candidate_parts']
    assert 'budget' in result['decision_trace']['rejected_unquoted_requirements']


def test_multiple_questions_are_not_silently_shown():
    with pytest.raises(DecisionError):parse_decision(response(next_question={'key':'multi','text':'预算多少？供电多少？','reason':'fixture','choices':[]}))
    with pytest.raises(DecisionError):parse_decision('not json')


@pytest.mark.asyncio
async def test_hunyuan_tc3_endpoint_and_builtin_search_disabled(monkeypatch):
    monkeypatch.setenv('DECISION_PROVIDER','legacy_hunyuan_tc3')
    monkeypatch.setenv('TENCENTCLOUD_SECRET_ID','fixture-id');monkeypatch.setenv('TENCENTCLOUD_SECRET_KEY','fixture-key')
    def handler(req):
        assert str(req.url)=='https://hunyuan.ai.tencentcloudapi.com/'
        assert req.headers['X-TC-Action']=='ChatCompletions' and '/hunyuan/tc3_request' in req.headers['Authorization']
        body=json.loads(req.content)
        assert body['EnableEnhancement'] is False and body['Messages'][0]['Content']=='test'
        return httpx.Response(200,json={'Response':{'Choices':[{'Message':{'Content':'OK'}}],'RequestId':'fixture-id-safe','Usage':{'TotalTokens':2}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        text,meta=await model_call([{'role':'user','content':'test'}],client)
    assert text=='OK' and meta['builtin_search_enabled'] is False


@pytest.mark.asyncio
async def test_model_error_preserves_code_but_not_secret_message(monkeypatch):
    monkeypatch.setenv('DECISION_PROVIDER','legacy_hunyuan_tc3')
    monkeypatch.setenv('TENCENTCLOUD_SECRET_ID','fixture-id');monkeypatch.setenv('TENCENTCLOUD_SECRET_KEY','fixture-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'Response':{'Error':{'Code':'UnauthorizedOperation','Message':'fixture-key'},'RequestId':'safe-rid'}}))) as client:
        with pytest.raises(DecisionError) as captured:await model_call([{'role':'user','content':'test'}],client)
    assert captured.value.code=='UnauthorizedOperation' and captured.value.request_id=='safe-rid'
    assert 'fixture-key' not in captured.value.message


def test_config_endpoint_never_echoes_or_writes_key():
    client=TestClient(app)
    key='synthetic-tokenhub-key-for-tests'
    response=client.post('/api/hardware/decision-config',json={'api_key':key,'model':'hy4-preview','region':'guangzhou'})
    assert response.status_code==200 and key not in response.text
    assert response.json()['storage']=='backend_process_environment_only'
    bad=client.post('/api/hardware/decision-config',json={'api_key':'AKID-not-a-tokenhub-key','model':'test'})
    assert bad.status_code==422 and 'AKID-not-a-tokenhub-key' not in bad.text


@pytest.mark.asyncio
async def test_tokenhub_uses_dedicated_bearer_not_cloud_akid(monkeypatch):
    monkeypatch.setenv('TOKENHUB_API_KEY','synthetic-tokenhub-key')
    monkeypatch.setenv('TOKENHUB_MODEL','hy4-preview')
    def handler(request):
        assert str(request.url)=='https://tokenhub.tencentmaas.com/v1/chat/completions'
        assert request.headers['Authorization']=='Bearer synthetic-tokenhub-key'
        body=json.loads(request.content)
        assert body['model']=='hy4-preview' and 'enable_enhancement' not in body
        return httpx.Response(200,json={'id':'fixture-tokenhub-request','choices':[{'message':{'content':'OK'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        text,meta=await model_call([{'role':'user','content':'test'}],client)
    assert text=='OK' and meta['provider']=='tokenhub'


@pytest.mark.asyncio
async def test_tokenhub_structured_task_uses_documented_response_format(monkeypatch):
    monkeypatch.setenv('TOKENHUB_API_KEY','synthetic-tokenhub-key')
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}
    def handler(request):
        body=json.loads(request.content)
        assert body['response_format']['type']=='json_schema'
        assert body['response_format']['json_schema']['schema']==schema
        return httpx.Response(200,json={'id':'fixture-json-request','choices':[{'message':{'content':'{"ok":true}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        text,meta=await model_call([{'role':'user','content':'Return JSON'}],client,response_schema=schema)
    assert json.loads(text)['ok'] and meta['response_format']=='json_schema'


@pytest.mark.asyncio
async def test_complex_plan_can_use_json_mode_with_local_schema_validation(monkeypatch):
    monkeypatch.setenv('TOKENHUB_API_KEY','synthetic-tokenhub-key')
    def handler(request):
        assert json.loads(request.content)['response_format']=={'type':'json_object'}
        return httpx.Response(200,json={'id':'fixture-json-mode','choices':[{'message':{'content':'{"ok":true}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        text,meta=await model_call([{'role':'user','content':'Return JSON'}],client,json_mode=True)
    assert json.loads(text)['ok'] and meta['response_format']=='json_object'


@pytest.mark.asyncio
async def test_credentials_in_message_are_not_forwarded():
    calls=[]
    async def caller(messages):calls.append(messages);return response(),{}
    with pytest.raises(DecisionError):
        await decide(DialogueRequest(message='AKID'+'Z'*32),caller=caller)
    assert not calls


@pytest.mark.asyncio
async def test_invalid_multiple_question_output_gets_one_real_model_repair(tmp_path,monkeypatch):
    import app.decision as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    calls=[]
    async def caller(messages):
        calls.append(messages)
        content=response(next_question={'key':'multi','text':'预算多少？供电多少？','reason':'synthetic','choices':[]}) if len(calls)==1 else response()
        return content,{'request_id':'synthetic-'+str(len(calls))}
    result=await decide(DialogueRequest(message='我只考虑红外'),caller=caller)
    assert len(calls)==2 and 'MultipleQuestions' in calls[1][-1]['content']
    assert result['decision_trace']['new_model_requests']==2
    assert result['decision_trace']['model_calls'][1]['purpose']=='repair_invalid_structured_decision'
