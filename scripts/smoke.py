"""Generate an honest offline acceptance record. Does not contact SearchPro."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from fastapi.testclient import TestClient
from app.main import app

for env_name in ("TENCENTCLOUD_WSA_APIKEY", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENTCLOUD_TOKEN", "SEARCHPRO_AUTH_MODE"):
    os.environ.pop(env_name, None)
client = TestClient(app)
scenarios = client.get("/api/scenarios").json()
records = []
for scenario in scenarios:
    payload = {"problem_text": scenario["text"], "constraints": scenario["constraints"], "search_mode": "mock"}
    payload.update({k: scenario[k] for k in ("claim", "profile", "signal_context") if k in scenario})
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["search"]["request_count"] == 0
    if scenario["id"] == "synthetic-color-line":
        assert "line_tracking" in result["problem"]["tasks"]
        assert not any(c["verdict"] == "pass" for c in result["recommendations"]), "Legacy single voltage must not prove full compatibility"
    if scenario["id"] == "synthetic-budget-conflict":
        assert not any(c["verdict"] == "pass" for c in result["recommendations"])
    records.append({"scenario": scenario["id"], "http_status": response.status_code, "summary": result["summary"], "mode": result["mode"], "request_count": 0,
                    "verdicts": {c["hardware"]["id"]: c["verdict"] for c in result["recommendations"]}})
    (root / "artifacts" / f'{scenario["id"]}-mock.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
live_error = client.post("/api/analyze", json={"problem_text": "颜色识别必须UART", "search_mode": "live"}).json()
assert live_error["search"]["status"] == "error" and live_error["search"]["request_count"] == 0
report = {"verified_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "type": "offline_mock_acceptance", "scenarios": records,
          "missing_key_honest_error": True, "real_searchpro_calls_performed": 0,
          "not_covered_by_this_offline_run": ["本记录仅为离线验收；真实查询以artifacts/live/manifest.json为准", "硬件实测", "公开部署", "正式比赛提交"]}
(root / "artifacts" / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
