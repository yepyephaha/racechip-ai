import asyncio
import json
from uuid import uuid4

import pytest

import app.fact_check as fc
from app.evidence_reader import public_target, relevant_windows


def plan():
    return {"subject":"RP2040 GPIO电平", "questions":["芯片IO是否耐5V"], "ambiguities":["开发板输入和GPIO要区分"], "official_domains":["vendor.example"], "reading_terms":["GPIO","3.3"], "queries":[{"angle":angle,"query":f"RP2040 GPIO {angle} {n}"} for angle in ('official','experience','counterexample','conditions') for n in range(3)]}


def report():
    return {"headline":"需区分供电输入和GPIO", "summary":"仅按本次原文核对，不推断全部开发板。", "findings":[{"statement":"该芯片的数字引脚工作在3.3V", "verdict":"supported", "explanation":"以对应芯片资料为准。", "conditions":["不是开发板的USB输入"], "citations":[{"source_id":"S1","quote":"Digital pins operate at 3.3 V."}]}], "user_experiences":[{"observation":"一位用户报告了测量差异", "context":"其特定开发板", "limitation":"不能替代厂商参数", "citations":[{"source_id":"S4","quote":"I measured this on my own board."}]}], "disagreements":[], "missing":[], "next_steps":["确认精确开发板"], "independence_note":"来源数量不等于独立验证次数。"}


def new_job():
    return {"id":str(uuid4()),"input":{"statement":"RP2040的GPIO可以直接接5V吗？","context":"","depth":"standard"},"status":"queued","phase":"等待","created_at":fc.now(),"planned_queries":0,"search_request_count":0,"read_count":0,"request_ids":[],"search_records":[],"model_calls":[],"sources":[],"report":None,"error":None,"warnings":[]}


def test_monitor_change_detection_uses_last_successful_snapshot_after_error():
    job=new_job()
    job.update(status='complete',report=report(),updated_at=fc.now(),sources=[{'id':'S1','url':'https://vendor.example/spec','title':'厂商规格','kind':'official','read_status':'read'}])
    previous=fc.snapshot(job)
    monitor={'id':str(uuid4()),'enabled':True,'interval_hours':24,'history':[{'job_id':None,'status':'error','changed':None},{'job_id':job['id'],'status':'running','changed':None}], 'last_snapshot':previous,'change_count':0}

    fc.finish_monitor_run(monitor,job)

    assert monitor['history'][-1]['changed'] is False
    assert monitor['history'][-1]['new_sources']==[]
    assert monitor['last_snapshot']['report_fingerprint']==previous['report_fingerprint']


def test_monitor_snapshot_marks_new_sources_and_only_explicit_publisher_dates():
    previous_job=new_job()
    previous_job.update(status='complete',report=report(),sources=[{'id':'S1','url':'https://vendor.example/spec','title':'规格','kind':'official','read_status':'read'}])
    previous=fc.snapshot(previous_job)
    latest=new_job()
    latest.update(status='complete',report=report(),sources=[
        {'id':'S1','url':'https://vendor.example/spec/','title':'规格','kind':'official','read_status':'read'},
        {'id':'S2','url':'https://forum.example/correction','title':'纠正帖','kind':'community','read_status':'read','published_at':'2026-10-24'}
    ])

    current=fc.snapshot(latest,previous)

    assert [item['title'] for item in current['new_sources']]==['纠正帖']
    assert current['new_sources'][0]['published_at']=='2026-10-24'


@pytest.mark.asyncio
async def test_nonvision_topic_uses_all_angles_and_actual_citations(tmp_path, monkeypatch):
    monkeypatch.setattr(fc,'ROOT',tmp_path)
    calls=[]
    async def model(messages):
        calls.append(messages)
        return json.dumps(plan() if len(calls)==1 else report()),{'model':'synthetic-model','request_id':'fixture-model-'+str(len(calls))}
    queries=[]
    async def search(mode,items):
        queries.extend(items)
        host='vendor.example' if 'official' in items[0] else 'forum.example'
        return {'status':'ok','request_count':1,'request_ids':['fixture-search-'+str(len(queries))],'query_records':[], 'results':[{'url':f'https://{host}/{len(queries)}','title':'合成资料，非真实实验','snippet':'fixture'}], 'error':None}
    async def reader(source,terms):
        return {**source,'read_status':'read','_chunks':[{'locator':'合成原文片段','text':'Digital pins operate at 3.3 V. I measured this on my own board.'}]}
    monkeypatch.setattr(fc,'model_call',model)
    job=new_job();fc.save(job)
    await fc.investigate(job['id'],search,reader)
    result=fc.read(job['id'])
    assert result['status']=='complete' and result['search_request_count']==12
    assert all('RP2040' in q and 'OpenMV' not in q and 'vision' not in q for q in queries)
    assert len(result['sources'])==12 and result['read_count']==6
    assert result['report']['findings'][0]['verdict']=='supported'
    assert result['report']['user_experiences'][0]['citations'][0]['source_id']=='S4'
    assert all('_chunks' not in s and '_snippet' not in s for s in fc.public(result)['sources'])


def test_fabricated_or_search_only_quotes_never_confirm_claims():
    r=fc.Report.model_validate(report())
    sources=[{'id':'S1','kind':'official','read_status':'unavailable','_chunks':[]}, {'id':'S4','kind':'community','read_status':'read','_chunks':[{'text':'Actual content differs.','locator':'网页'}]}]
    result=fc.validated_report(r,sources)
    assert result['findings'][0]['verdict']=='insufficient'
    assert result['findings'][0]['citations']==[] and not result['user_experiences']
    assert result['headline'].startswith('证据不足')


def test_community_opinion_is_not_promoted_to_official_specification():
    r=fc.Report.model_validate(report())
    source={'id':'S1','kind':'community','read_status':'read','_chunks':[{'locator':'用户帖子','text':'Digital pins operate at 3.3 V.'}]}
    result=fc.validated_report(r,[source])
    assert result['findings'][0]['verdict']=='insufficient'


@pytest.mark.asyncio
async def test_search_auth_failure_stops_further_paid_queries(tmp_path, monkeypatch):
    monkeypatch.setattr(fc,'ROOT',tmp_path)
    async def model(messages):return json.dumps(plan()),{'model':'fixture'}
    monkeypatch.setattr(fc,'model_call',model)
    count=0
    async def search(mode,queries):
        nonlocal count
        count+=1
        return {'status':'error','request_count':1,'request_ids':[],'results':[],'error':'SearchPro HTTP 403','query_records':[]}
    job=new_job();fc.save(job)
    await fc.investigate(job['id'],search)
    result=fc.read(job['id'])
    assert count==1 and result['status']=='error' and result['search_request_count']==1


def test_cancel_flag_survives_a_progress_write(tmp_path, monkeypatch):
    monkeypatch.setattr(fc,'ROOT',tmp_path)
    job=new_job();fc.save(job)
    stored=fc.read(job['id']);stored['cancel_requested']=True;fc.save(stored)
    job['phase']='旧内存中的下一步';fc.save(job)
    assert fc.read(job['id'])['cancel_requested']


@pytest.mark.asyncio
@pytest.mark.parametrize('url',['http://127.0.0.1/key','http://169.254.169.254/latest','http://[::1]/','https://user:pass@example.com/','https://example.com:8000/'])
async def test_reader_blocks_private_and_credential_urls(url):
    with pytest.raises(ValueError):await public_target(url)


def test_relevant_pdf_windows_retain_page_locations():
    chunks=[{'locator':'PDF 第1页','text':'Introduction '*300}, {'locator':'PDF 第34页','text':'Electrical conditions. GPIO max voltage table 3.3 V.'}]
    selected=relevant_windows(chunks,['GPIO','voltage'])
    assert selected[0]['locator']=='PDF 第34页'


def test_source_role_has_no_catalog_dependency():
    assert fc.source_kind('https://vendor.example/doc',['vendor.example'])=='official'
    assert fc.source_kind('https://forum.another-device.org/topic',[])=='community'
    assert fc.source_kind('https://vendor.example.evil.test/doc',['vendor.example'])!='official'
    assert fc.source_kind('https://forum.vendor.example/topic',['vendor.example'])=='community'


@pytest.mark.asyncio
async def test_proxy_benchmark_dns_is_resolved_independently(monkeypatch):
    import app.evidence_reader as reader
    import socket
    monkeypatch.setattr(reader.socket,'getaddrinfo',lambda *args:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('198.18.1.2',443)),(socket.AF_INET6,socket.SOCK_STREAM,6,'',('2001:2::123',443,0,0))])
    asked=[]
    async def doh(host):asked.append(host);return ['93.184.216.34']
    monkeypatch.setattr(reader,'doh_addresses',doh)
    target,host=await reader.public_target('https://vendor.example/docs')
    assert target=='https://93.184.216.34/docs' and host=='vendor.example' and asked==['vendor.example']


@pytest.mark.asyncio
async def test_dns_fallback_does_not_allow_private_destinations(monkeypatch):
    import app.evidence_reader as reader
    import socket
    monkeypatch.setattr(reader.socket,'getaddrinfo',lambda *args:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('198.18.1.2',443))])
    async def doh(host):return ['127.0.0.1']
    monkeypatch.setattr(reader,'doh_addresses',doh)
    with pytest.raises(ValueError):await reader.public_target('https://vendor.example/docs')


def test_title_only_web_page_is_not_counted_as_read_original():
    from app.evidence_reader import extract_document
    with pytest.raises(ValueError,match='标题'):
        extract_document(b'<html><title>ESP32 datasheet</title></html>','text/html','https://vendor.example/doc')


@pytest.mark.asyncio
async def test_unreadable_originals_do_not_trigger_a_model_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(fc,'ROOT',tmp_path)
    async def model(messages):raise AssertionError('No model report should be generated without originals')
    monkeypatch.setattr(fc,'model_call',model)
    async def reader(source,terms):return {**source,'read_status':'unavailable','read_error':'fixture blocked','_chunks':[]}
    job=new_job();job['sources']=[{'id':'S1','url':'https://vendor.example/doc','kind':'official','title':'fixture','queries':[],'read_status':'not_selected'}]
    fc.save(job)
    await fc.finish_sources(job,fc.Plan.model_validate(plan()),reader)
    assert job['status']=='partial' and job['report'] is None and job['model_calls']==[]
