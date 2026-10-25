import json

import pytest
from fastapi.testclient import TestClient

from app.claim_checks import audit_claim
from app.main import app, load_data
from app.models import Claim, Constraints, Profile, SignalContext
from app.engine import evaluate_catalog
from app.parser import parse_problem
from app.source_review import plain_text
from app.suitability import apply_profile


def claim(field="io_tolerance", model="openmv-rt1062", text="RT1062可以安全接收5V", **kw):
    return Claim(field=field, hardware_id=model, text=text, **kw)


def reviews(model="openmv-rt1062", field="io_input_max_v", url="https://openmv.io/products/openmv-cam-rt"):
    return [{"status": "matched", "hardware_id": model, "fields": [field], "evidence_id": "synthetic-review", "url": url}]


def test_domain_match_without_original_is_insufficient():
    result = audit_claim(claim(), SignalContext(direction="to_board", voltage_v=5, pin="UART RX", level_shifter=False), load_data("catalog.json"), [])
    assert result[0]["status"] == "insufficient"


def test_rt_5v_claim_contradicted_by_exact_original():
    result = audit_claim(claim(), SignalContext(direction="to_board", voltage_v=5, pin="UART RX", level_shifter=False), load_data("catalog.json"), reviews())
    assert result[0]["status"] == "contradicted"
    assert result[0]["hardware_reproduced"] is False


def test_h7_facts_do_not_transfer_to_rt():
    result = audit_claim(claim(), SignalContext(direction="to_board", voltage_v=5, pin="UART RX", level_shifter=False), load_data("catalog.json"), reviews("openmv-h7-plus"))
    assert result[0]["status"] == "insufficient"


def test_supply_or_direction_missing_is_not_compatible():
    result = audit_claim(claim(), SignalContext(), load_data("catalog.json"), reviews())
    assert result[0]["status"] == "insufficient"
    problem, c, _ = parse_problem("颜色识别供电5V", Constraints(logic_voltage_v=3.3))
    assert all(r["verdict"] != "pass" for r in evaluate_catalog(load_data("catalog.json"), c, problem))


def test_community_sensor_difference_not_fabrication():
    url = "https://forums.openmv.io/t/higher-fps-from-openmv-cam-h7-plus-and-mt9v034/5585"
    result = audit_claim(claim("algorithm_fps", "openmv-h7-plus", "高帧率例程保证100FPS", source_url=url, sensor="OV5640"), SignalContext(), load_data("catalog.json"), reviews("openmv-h7-plus", "engineering_experience", url))
    assert result[0]["status"] == "conditions_differ"


def test_lifecycle_supported_is_separate_from_fit():
    result = audit_claim(claim("lifecycle", "openmv-h7-plus", "H7 Plus已经停止常规生产"), SignalContext(), load_data("catalog.json"), reviews("openmv-h7-plus", "caveats"))
    assert result[0]["status"] == "supported"


def test_owned_hardware_changes_fit_not_facts_or_fail():
    problem, c, _ = parse_problem("离线颜色巡线", Constraints(banned_hardware=["OpenMV"]))
    recs = evaluate_catalog(load_data("catalog.json"), c, problem)
    before = next(r for r in recs if r["hardware"]["id"] == "openmv-h7-plus")["verdict"]
    fitted = apply_profile(recs, Profile(existing_hardware=["openmv-h7-plus"], available_hours=2), True)
    selected = next(r for r in fitted if r["hardware"]["id"] == "openmv-h7-plus")
    assert selected["verdict"] == before == "fail"
    assert selected["suitability"]["owned"] is True
    assert all(r["verdict"] == "fail" for r in fitted if r["hardware"]["id"] != "openmv-h7-plus")


def test_original_html_is_text_only():
    assert plain_text('<script>wrong</script><p>All I/O&nbsp;pins <b>output</b> 3.3V</p>') == "All I/O pins output 3.3V"


def test_recalculation_reuses_identified_evidence_not_new_network(monkeypatch):
    monkeypatch.delenv("TENCENTCLOUD_WSA_APIKEY", raising=False)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_KEY", raising=False)
    client = TestClient(app)
    payload = {"problem_text": "离线颜色巡线", "search_mode": "mock", "profile": {"existing_hardware": []}}
    first = client.post("/api/analyze", json=payload).json()
    payload.update(reuse_case_id=first["case_id"], profile={"existing_hardware": ["openmv-h7-plus"]},
                   previous_inputs={"constraints": first["constraints"], "profile": first["profile"], "signal_context": first["signal_context"]})
    second = client.post("/api/analyze", json=payload).json()
    assert second["change_summary"]["new_search_requests"] == 0
    assert second["change_summary"]["reused_evidence"] and second["change_summary"]["changes"]
    assert second["search"]["mode"] == "mock"
    payload["problem_text"] = "离线AprilTag定位"
    assert client.post("/api/analyze", json=payload).status_code == 422
