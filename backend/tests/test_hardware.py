import copy
import io
import json
from datetime import datetime, timezone
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.hardware_models import HardwareProject, DialogueRequest
from app.hardware_service import dialogue, review_project, reference_catalog, numeric_fact, price_leads
import app.hardware_api as hardware_api


def sample():
    return HardwareProject(name="合成测试项目",domain="iot",budget_cny=100,bom=[{"ref":"P1","part_id":"ti-lm2596-evm"},{"ref":"S1","part_id":"bosch-bme280"}],connections=[{"from_ref":"P1","to_ref":"S1","kind":"power"}])


def test_progressive_one_question_and_no_reasking_known_facts():
    first=dialogue(DialogueRequest(message="做电池供电的温湿度WiFi节点，预算300元"))
    assert first["assistant"]["question_key"]=="resources"
    assert first["project"]["requirements"]["power_source"]=="电池供电"
    assert len([m for m in first["history"] if m["role"]=="assistant"])==1
    second=dialogue(DialogueRequest(project=first["project"],pending_key="resources",message="有C基础和万用表",history=first["history"]))
    assert second["ready"] and second["assistant"]["question_key"] is None


def test_line_follower_not_forced_into_camera_only_route():
    first=dialogue(DialogueRequest(message="我现在要设计一辆小车循迹，需要什么模块"))
    assert first['project']['domain']=='robotics'
    second=dialogue(DialogueRequest(project=first['project'],history=first['history'],message='电池供电',pending_key=first['assistant']['question_key']))
    assert second['assistant']['question_key']=='tracking_method'


def test_power_question_is_skipped_when_input_already_states_io():
    result=dialogue(DialogueRequest(message="做12V转5V的3A稳压电源"))
    assert result["assistant"]["question_key"]!="power_io"
    assert result["project"]["requirements"]["power_io"]


def test_answer_can_resolve_multiple_followups_at_once():
    first=dialogue(DialogueRequest(message="做一个温湿度无线节点"))
    second=dialogue(DialogueRequest(project=first["project"],history=first["history"],pending_key=first["assistant"]["question_key"],message="USB供电，WiFi联网，预算600元，已有C基础和万用表"))
    assert second["ready"]
    assert second["project"]["budget_cny"]==600


def test_later_constraint_overrides_old_conversation_value():
    first=dialogue(DialogueRequest(message='电池供电WiFi节点，预算300元'))
    changed=dialogue(DialogueRequest(project=first['project'],history=first['history'],message='改用USB供电，预算改为600元'))
    assert changed['project']['budget_cny']==600
    assert changed['project']['requirements']['power_source']=='USB供电'


def test_product_link_is_specific_not_search_or_spoofed_domain():
    from app.hardware_service import product_link
    assert product_link("https://item.taobao.com/item.htm?id=123")["product_url"]
    assert product_link("https://item.szlcsc.com/117967.html")["product_url"]
    assert product_link("https://s.taobao.com/search?q=BME280")["product_url"] is None
    assert product_link("https://item.taobao.com.evil.test/item.htm?id=123")["product_url"] is None


def test_unknown_answer_advances_without_filling_fake_numbers():
    first=dialogue(DialogueRequest(message="做一个温湿度无线节点"))
    second=dialogue(DialogueRequest(project=first["project"],pending_key=first["assistant"]["question_key"],message="还不清楚"))
    assert second["assistant"]["question_key"]!=first["assistant"]["question_key"]
    assert second["project"]["budget_cny"] is None


def test_actual_source_ranges_expose_power_conflict():
    result=review_project(sample())
    assert result["verdict"]=="fail"
    assert result["checks"][0]["status"]=="fail" and "3.6" in result["checks"][0]["reason"]
    assert result["checks"][0]["evidence"]


def test_unknown_prices_are_not_zero_total():
    result=review_project(sample())
    assert result["budget"]["known_subtotal_cny"]==0
    assert result["budget"]["total_cny"] is None
    assert result["budget"]["status"]=="unknown"


def test_quantity_quote_and_partial_cost_accounting():
    project=sample();project.bom[0].quantity=3;project.bom[0].unit_price_cny=40
    result=review_project(project)
    assert result["budget"]["known_subtotal_cny"]==120 and result["budget"]["status"]=="fail"
    assert result["budget"]["total_cny"] is None


def test_quote_lead_is_not_verified_price():
    project=sample();project.budget_cny=1000
    for line in project.bom:
        line.unit_price_cny=20;line.quote_source="https://example.invalid/synthetic";line.quote_at=datetime.now(timezone.utc);line.quote_kind="search_lead"
    result=review_project(project)
    assert result["budget"]["status"]=="unknown"
    assert not any(l["is_market_verified"] for l in result["bom"])


def test_custom_part_cannot_self_certify_or_override_catalog():
    project=HardwareProject(custom_parts=[{"id":"mine","name":"合成器件","facts":{"supply_max_v":{"value":100,"unit":"V","status":"source_checked"}}}])
    from app.hardware_service import resolve_parts
    assert resolve_parts(project)["mine"]["facts"]["supply_max_v"]["status"]=="user_asserted"
    project.custom_parts[0].id="bosch-bme280"
    with pytest.raises(ValueError):resolve_parts(project)


def test_units_cannot_turn_amps_into_volts():
    assert numeric_fact({"facts":{"supply_max_v":{"value":100,"unit":"A","status":"source_checked"}}},"supply_max_v") is None
    assert numeric_fact({"facts":{"supply_max_v":{"value":3600,"unit":"mV","status":"source_checked"}}},"supply_max_v")==3.6


def test_change_impact_tracks_neighboring_checks():
    before=sample();after=before.model_copy(deep=True);after.bom[0].part_id="ti-lm2596-adj"
    result=review_project(after,before)
    assert result["change_impact"][0]["affected_checks"]
    assert result["checks"][0]["status"]=="unknown"
    assert result["verification_actions"][0]["executed"] is False


def test_multiple_sku_prices_do_not_pick_cheapest():
    result=price_leads([{"id":"fixture","title":"BME280模块","snippet":"￥5.0和￥20.0不同套装","url":"https://example.invalid/sku","kind":"search_lead","source":"synthetic"}],"BME280")
    assert result[0]["amount_cny"] is None
    assert result[0]["quote_type"]=="multiple_skus_or_tiers"


def test_similar_part_name_is_not_a_matching_product_quote():
    hits=[{"id":"fixture","title":"BMP280","snippet":"BMP280模块报价￥10","url":"https://item.szlcsc.com/123.html","kind":"search_lead","source":"fixture"}]
    assert price_leads(hits,'BME280')==[]


def test_starting_price_and_foreign_currency_not_bom_quote():
    hits=[{"id":"fixture","title":"BME280","snippet":"￥5.00起","url":"https://example.invalid/sku","kind":"search_lead","source":"synthetic"}]
    result=price_leads(hits,"BME280")[0]
    assert result["quote_type"]=="starting_price" and result["status"]=="needs_sku_confirmation"
    hits[0]["snippet"]="$5 USD"
    assert price_leads(hits,"BME280")[0]["amount_cny"] is None


def test_yen_and_thousands_separator_not_misread_as_one_yuan():
    hits=[{"id":"fixture","title":"BME280","snippet":"JPY ¥1,575 / Qty2 ¥1,480","url":"https://www.waveshare.com/currency/JPY/","kind":"search_lead","source":"synthetic"}]
    result=price_leads(hits,"BME280")[0]
    assert result["currency"]=='JPY' and result["amount_cny"] is None
    assert result["price_candidates_original"]==[1480,1575]
    hits[0].update(url="https://item.szlcsc.com/123.html",snippet="BME280 含税人民币 ¥1,575.25 单只报价")
    assert price_leads(hits,"BME280")[0]["amount_cny"]==1575.25


def test_qna_cites_uploaded_page_without_inventing_answer(tmp_path,monkeypatch):
    monkeypatch.setattr(hardware_api,"RUNTIME",tmp_path)
    client=TestClient(app)
    doc=client.post("/api/hardware/documents",json={"name":"synthetic datasheet","text":"Supply voltage VDD is 1.71 V to 3.6 V. This is synthetic test content."}).json()
    answer=client.post("/api/hardware/qa",json={"question":"VDD供电电压是多少","document_ids":[doc["id"]]}).json()
    assert answer["citations"][0]["page"]==1 and "3.6" in answer["answer"]
    unknown=client.post("/api/hardware/qa",json={"question":"扭矩和齿轮减速比","document_ids":[doc["id"]]}).json()
    assert not unknown["citations"] and "未找到" in unknown["answer"]


def test_csv_import_and_export_is_usable_handoff():
    client=TestClient(app)
    imported=client.post("/api/hardware/import-bom",json={"csv_text":"ref,mpn,quantity,unit_price_cny\nU1,UNO R3,2,10\nU2,custom-sensor,0,2"}).json()
    assert imported["bom"][0]["quantity"]==2 and imported["errors"]
    response=client.post("/api/hardware/export",json={"project":sample().model_dump(mode="json")})
    assert response.status_code==200
    with ZipFile(io.BytesIO(response.content)) as bundle:
        assert {"bom.csv","connections.csv","architecture.mmd","handoff-netlist.json","verification-plan.md"}.issubset(bundle.namelist())
        assert "BME280" in bundle.read("bom.csv").decode("utf-8-sig")


def test_export_retains_actual_saved_search_trace(tmp_path,monkeypatch):
    monkeypatch.setattr(hardware_api,'RUNTIME',tmp_path)
    client=TestClient(app)
    project=sample().model_dump(mode='json')
    reviewed=client.post('/api/hardware/review',json={'project':project,'search_mode':'mock'}).json()
    response=client.post('/api/hardware/export',json={'project':reviewed['project'],'review_id':reviewed['review_id']})
    with ZipFile(io.BytesIO(response.content)) as bundle:
        record=json.loads(bundle.read('saved-search-review.json'))
        assert record['same_project_inputs'] and record['historical_record']
        assert record['record']['search']['mode']=='mock'


def test_pdf_upload_and_page_citation(tmp_path,monkeypatch):
    monkeypatch.setattr(hardware_api,'RUNTIME',tmp_path)
    content=b'BT /F1 12 Tf 72 700 Td (Synthetic supply voltage VDD 1.71 V to 3.6 V.) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'\nendstream']
    data=bytearray(b'%PDF-1.4\n');offsets=[]
    for i,obj in enumerate(objects,1):offsets.append(len(data));data.extend(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
    xref=len(data);data.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for offset in offsets:data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
    client=TestClient(app)
    uploaded=client.post('/api/hardware/documents/pdf?name=synthetic.pdf',content=bytes(data),headers={'Content-Type':'application/pdf'})
    assert uploaded.status_code==200,uploaded.text
    answer=client.post('/api/hardware/qa',json={'question':'VDD供电电压','document_ids':[uploaded.json()['id']]}).json()
    assert answer['citations'][0]['page']==1 and '3.6' in answer['answer']
    assert client.post('/api/hardware/documents/pdf',content=b'not a pdf').status_code==422


def test_project_save_load_and_invalid_connection(tmp_path,monkeypatch):
    monkeypatch.setattr(hardware_api,"RUNTIME",tmp_path)
    client=TestClient(app)
    stored=client.post("/api/hardware/projects",json=sample().model_dump(mode="json")).json()
    assert client.get("/api/hardware/projects/"+stored["id"]).json()["name"]=="合成测试项目"
    invalid=sample().model_dump(mode="json");invalid["connections"][0]["to_ref"]="missing"
    assert client.post("/api/hardware/review",json={"project":invalid}).status_code==422


def test_product_search_and_price_modes_are_yuanbao_or_marked_mock():
    client=TestClient(app)
    result=client.post("/api/hardware/prices",json={"mpn":"BME280","mode":"mock"}).json()
    assert result["search"]["request_count"]==0 and not result["price_leads"]
    assert "元宝" in result["policy"]
