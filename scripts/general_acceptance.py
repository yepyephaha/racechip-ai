"""Exercise general hardware workflow. Only explicit live steps call Yuanbao SearchPro."""
import io
import json
from pathlib import Path
from datetime import datetime,timezone
from zipfile import ZipFile
import httpx

root=Path(__file__).resolve().parents[1]
folder=root/"artifacts/general"
folder.mkdir(exist_ok=True)
report={"executed_at":datetime.now(timezone.utc).isoformat(),"search_provider":"Yuanbao SearchPro","checks":[],"search_request_count":0}
with httpx.Client(base_url="http://127.0.0.1:8000",timeout=160) as client:
    health=client.get('/api/health').json()
    assert health['version']=='0.3.0' and health['search_configured']
    first=client.post('/api/hardware/dialogue',json={"message":"做电池供电的温湿度WiFi节点，预算300元","decision_mode":"rules_demo"}).json()
    assert first['assistant']['question_key']=='resources'
    second=client.post('/api/hardware/dialogue',json={"project":first['project'],"message":"有C基础和万用表","pending_key":first['assistant']['question_key'],"history":first['history'],"decision_mode":"rules_demo"}).json()
    assert second['ready']
    (folder/'dialogue-rules-demo.json').write_text(json.dumps(second,ensure_ascii=False,indent=2),encoding='utf-8')
    report['checks'].append({'step':'explicit_rules_demo_only','status':'pass','method':second['method'],'validates_model_decision':False,'candidate_count':len(second['candidate_parts'])})
    example=client.get('/api/hardware/examples').json()[0]['project']
    response=client.post('/api/hardware/review',json={'project':example,'search_mode':'live'})
    response.raise_for_status();data=response.json()
    assert data['verdict']=='fail' and any(c['status']=='fail' for c in data['checks'])
    (folder/'general-live-review.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    report['checks'].append({'step':'general_live_review','status':data['search']['status'],'conflict_found':True,'request_ids':data['search']['request_ids']})
    report['search_request_count']+=data['search']['request_count']
    price=client.post('/api/hardware/prices',json={'mpn':'BME280','item_type':'温湿度传感器模块','mode':'live'})
    price.raise_for_status();price=price.json()
    assert price['search']['status']=='ok'
    (folder/'yuanbao-price-leads.json').write_text(json.dumps(price,ensure_ascii=False,indent=2),encoding='utf-8')
    report['checks'].append({'step':'yuanbao_market_price_search','status':price['search']['status'],'request_ids':price['search']['request_ids'],'leads':len(price['price_leads']),'product_links':sum(bool(x['product_url']) for x in price['price_leads']),'single_price_leads':sum(x['amount_cny'] is not None for x in price['price_leads']),'sku_verified':False})
    report['search_request_count']+=price['search']['request_count']
    changed=json.loads(json.dumps(example));changed['bom'][2]['part_id']='ti-lm2596-adj'
    change=client.post('/api/hardware/review',json={'project':changed,'previous_project':example,'search_mode':'off'}).json()
    assert change['change_impact'] and change['search']['request_count']==0
    (folder/'change-impact.json').write_text(json.dumps(change,ensure_ascii=False,indent=2),encoding='utf-8')
    compare=client.post('/api/hardware/compare',json={'project':example,'part_ids':['ti-lm2596-evm','ti-lm2596-adj']}).json()
    assert compare['rows'] and compare['replacement_status'].startswith('needs_')
    report['checks'].append({'step':'compare_and_change_impact','status':'pass','new_requests':0})
    doc=client.post('/api/hardware/documents',json={'name':'合成问答测试摘录','text':'Supply voltage VDD is 1.71 V to 3.6 V. This is synthetic test content, not a manufacturer datasheet.'}).json()
    answer=client.post('/api/hardware/qa',json={'question':'VDD供电电压范围是多少','document_ids':[doc['id']]}).json()
    assert answer['citations'] and answer['citations'][0]['page']==1
    report['checks'].append({'step':'cited_document_qa','status':'pass','input':'explicit_synthetic_fixture'})
    export=client.post('/api/hardware/export',json={'project':example})
    export.raise_for_status();(folder/'hardware-handoff.zip').write_bytes(export.content)
    with ZipFile(io.BytesIO(export.content)) as z: assert 'bom.csv' in z.namelist() and 'handoff-netlist.json' in z.namelist()
    imported=client.post('/api/hardware/import-bom',json={'csv_text':'ref,mpn,quantity,unit_price_cny\nU1,UNO R3,2,10'}).json()
    assert imported['bom'][0]['quantity']==2
    report['checks'].append({'step':'bom_csv_and_engineering_export','status':'pass','native_eda':False})
(folder/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
