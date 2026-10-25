"""Synthetic fixtures exercise policy; these are not real SearchPro queries."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.engine import evaluate_catalog
from app.main import app, load_data
from app.models import Constraints
from app.parser import parse_problem
from app.search import ENDPOINT, parse_pages, run_search, safe_url


def fixture_board(**overrides):
    board = {"id": "fixture-board", "name": "Fixture Board", "vendor": "Fixture",
             "interfaces": ["UART"], "logic_voltage_v": 3.3, "price_cny": 100, "power_w": 2,
             "capabilities": ["color_tracking", "offline_inference"], "skill_level": 2, "docs_quality": 4,
             "caveats": [], "evidence": [{"id": f"fixture-{field}", "kind": "official", "status": "verified", "field": field,
                                          "url": "https://example.invalid/spec"}
                                         for field in ("interfaces", "logic_voltage_v", "price_cny", "power_w", "capabilities")]}
    board.update(overrides)
    return board


def parsed(text="颜色识别，必须UART，逻辑电平3.3V，离线运行", constraints=None):
    return parse_problem(text, constraints or Constraints())


def evaluate(board, constraints=None, text="颜色识别，必须UART，逻辑电平3.3V，离线运行", search=None):
    problem, merged, _ = parsed(text, constraints)
    return evaluate_catalog([board], merged, problem, search)[0]


def test_verified_constraints_pass():
    result = evaluate(fixture_board(), Constraints(budget_cny=100, max_power_w=2), text="颜色识别，必须UART，离线运行")
    assert result["verdict"] == "pass"
    assert result["score"] == sum(x["points"] for x in result["score_breakdown"])


@pytest.mark.parametrize("override,constraints", [
    ({"price_cny": None}, Constraints(budget_cny=100)),
    ({"power_w": None}, Constraints(max_power_w=3)),
    ({"evidence": []}, Constraints()),
    ({"interfaces": []}, Constraints(required_interfaces=["UART"])),
    ({"capabilities": []}, Constraints(offline_required=True)),
])
def test_missing_evidence_never_passes(override, constraints):
    assert evaluate(fixture_board(**override), constraints)["verdict"] == "unknown"


@pytest.mark.parametrize("override,constraints", [
    ({"price_cny": 101}, Constraints(budget_cny=100)),
    ({"power_w": 3}, Constraints(max_power_w=2)),
    ({}, Constraints(banned_hardware=["fixture"])),
])
def test_hard_conflicts_excluded(override, constraints):
    assert evaluate(fixture_board(**override), constraints)["verdict"] == "fail"


def test_negative_task_not_included():
    problem, _, _ = parsed("红色巡线，不需要目标检测")
    assert problem["tasks"] == ["color_tracking", "line_tracking"]


def test_units_and_strict_limit_merge():
    _, constraints, warnings = parsed("颜色识别，预算1千元，功耗不超过500mW，逻辑电平3.3V", Constraints(budget_cny=800))
    assert constraints.budget_cny == 800 and constraints.max_power_w == .5
    assert constraints.logic_voltage_v == 3.3 and warnings


def test_supply_is_not_logic_level():
    _, constraints, _ = parsed("颜色识别，供电5V，使用UART")
    assert constraints.logic_voltage_v is None


def test_unmodeled_performance_never_passes():
    assert evaluate(fixture_board(), text="颜色识别，处理速度必须30fps")["verdict"] == "unknown"


def test_conflicting_input_never_passes():
    assert evaluate(fixture_board(), Constraints(logic_voltage_v=5))["verdict"] != "pass"


def test_unknown_task_never_passes():
    assert evaluate(fixture_board(), text="请给出适合我的硬件选择建议")["verdict"] == "unknown"


def test_ban_from_problem_not_lost():
    assert evaluate(fixture_board(), text="颜色识别，禁止使用Fixture")["verdict"] == "fail"


def test_sort_never_rewards_a_conflict():
    problem, constraints, _ = parsed("颜色识别，必须UART，离线运行", Constraints(budget_cny=100))
    results = evaluate_catalog([fixture_board(id="fail", price_cny=1000), fixture_board(id="pass", docs_quality=1)], constraints, problem)
    assert [r["verdict"] for r in results] == ["pass", "fail"]


def test_official_pages_string_array_contract():
    payload = {"Response": {"Pages": [json.dumps({"title": "Test", "url": "https://example.org/doc", "passage": "test", "published_at": "2026-10-24"}), "broken", "{}", json.dumps({"url": "javascript:alert(1)"})]}}
    result = parse_pages(payload, 0)
    assert len(result) == 1 and result[0]["kind"] == "search_lead"
    assert result[0]["search_date_hint"] == "2026-10-24" and "published_at" not in result[0]


def test_page_errors_are_not_results():
    with pytest.raises(ValueError, match="UnauthorizedOperation"):
        parse_pages({"Response": {"Error": {"Code": "UnauthorizedOperation", "Message": "not exposed"}}}, 0)


@pytest.mark.asyncio
async def test_mock_never_calls_network():
    def reject(request):
        pytest.fail("mock mode attempted network")
    async with httpx.AsyncClient(transport=httpx.MockTransport(reject)) as client:
        result = await run_search("mock", ["test"] * 3, client)
    assert result["mode"] == "mock" and result["request_count"] == 0
    assert all(x["kind"] == "mock" and "MOCK" in x["title"] for x in result["results"])


@pytest.mark.asyncio
async def test_live_without_key_no_network(monkeypatch):
    monkeypatch.delenv("TENCENTCLOUD_WSA_APIKEY", raising=False)
    result = await run_search("live", ["test"])
    assert result["status"] == "error" and result["results"] == [] and result["request_count"] == 0


@pytest.mark.asyncio
async def test_live_request_contract_and_secret_not_in_output(monkeypatch):
    secret = "synthetic-test-secret-not-real"
    monkeypatch.setenv("TENCENTCLOUD_WSA_APIKEY", secret)
    def handler(request):
        assert str(request.url) == ENDPOINT
        assert request.headers["Authorization"] == "Bearer " + secret
        assert list(json.loads(request.content)) == ["Query"]
        return httpx.Response(200, json={"Response": {"Pages": [json.dumps({"title": "Fixture", "url": "https://example.org/doc", "passage": "Synthetic"})], "RequestId": "synthetic-request-id"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await run_search("live", ["test1", "test2", "test3"], client)
    assert result["status"] == "ok" and result["request_count"] == 3
    assert secret not in json.dumps(result)


@pytest.mark.asyncio
async def test_live_failure_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_WSA_APIKEY", "synthetic")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(429))) as client:
        result = await run_search("live", ["test"] * 3, client)
    assert result["status"] == "error" and result["mode"] == "live" and not result["results"]
    assert result["request_count"] == 1 and "429" in result["error"]


def test_failed_search_blocks_live_recommendation():
    result = evaluate(fixture_board(), search={"mode": "live", "status": "error", "results": []})
    assert result["verdict"] == "unknown"


def test_live_lead_does_not_overwrite_specs():
    search = {"mode": "live", "status": "ok", "results": [{"title": "Fixture", "snippet": "price 1", "url": "https://example.invalid/new"}]}
    result = evaluate(fixture_board(price_cny=None), Constraints(budget_cny=1), search=search)
    assert result["verdict"] == "unknown"
    assert result["hardware"]["price_cny"] is None


def test_link_validation():
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("https://secret@host.test/") is None
    assert safe_url("https://example.org/") == "https://example.org/"


def test_catalog_real_sources_and_no_invented_prices():
    records = load_data("catalog.json")
    assert len(records) >= 4 and len({h["id"] for h in records}) == len(records)
    for h in records:
        assert h["price_cny"] is None and h["power_w"] is None
        assert h["evidence"]
        assert all(safe_url(e["url"]) and e["accessed_at"] for e in h["evidence"])
        assert all(e["status"] == "needs_verification" for e in h["evidence"] if e["kind"] == "community")


def test_api_mock_scenario_and_validation(monkeypatch):
    monkeypatch.delenv("TENCENTCLOUD_WSA_APIKEY", raising=False)
    client = TestClient(app)
    assert client.get("/api/health").json()["search_configured"] is False
    scenarios = client.get("/api/scenarios").json()
    assert len(scenarios) >= 3
    for scenario in scenarios:
        response = client.post("/api/analyze", json={"problem_text": scenario["text"], "constraints": scenario["constraints"], "search_mode": "mock"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["search"]["request_count"] == 0 and body["mode"] == "mock"
        assert body["evidence"] and len(body["recommendations"]) >= 4
    assert client.post("/api/analyze", json={"problem_text": "   "}).status_code == 422
    assert client.post("/api/analyze", json={"problem_text": "颜色识别测试", "constraints": {"budget_cny": -1}}).status_code == 422
    assert client.post("/api/analyze", json={"problem_text": "颜色识别预算999999999元"}).status_code == 422


def test_api_live_without_key_honest_error(monkeypatch):
    monkeypatch.delenv("TENCENTCLOUD_WSA_APIKEY", raising=False)
    body = TestClient(app).post("/api/analyze", json={"problem_text": "颜色识别使用UART", "search_mode": "live"}).json()
    assert body["mode"] == "live" and body["search"]["status"] == "error"
    assert not any(r["verdict"] == "pass" for r in body["recommendations"])
