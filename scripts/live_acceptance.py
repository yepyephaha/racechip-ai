"""Run three actual questions against the local credentialed backend, without reading secrets."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

root = Path(__file__).resolve().parents[1]
folder = root / "artifacts" / "live"
folder.mkdir(exist_ok=True)
scenarios = json.loads((root / "data" / "investigations.json").read_text(encoding="utf-8"))
manifest = {"executed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "type": "actual_searchpro_queries", "cases": [], "new_request_count": 0}
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=160) as client:
    assert client.get("/api/health").json()["search_configured"], "Backend credentials are not configured"
    for scenario in scenarios:
        payload = {k: scenario[k] for k in ("constraints", "claim", "profile", "signal_context")}
        payload.update(problem_text=scenario["text"], search_mode="live")
        response = client.post("/api/analyze", json=payload)
        response.raise_for_status()
        result = response.json()
        (folder / (scenario["id"] + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        entry = {"id": scenario["id"], "case_id": result["case_id"], "created_at": result["created_at"],
                 "search_status": result["search"]["status"], "request_ids": result["search"]["request_ids"],
                 "request_count": result["search"]["request_count"], "result_count": len(result["search"]["results"]),
                 "claim_status": [c["status"] for c in result["claim_checks"]],
                 "matched_originals": sum(s["status"] == "matched" for s in result["source_reviews"]), "error": result["search"]["error"]}
        manifest["cases"].append(entry)
        manifest["new_request_count"] += entry["request_count"]
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if scenario["id"] == "case-c-lifecycle":
            payload.update(reuse_case_id=result["case_id"], previous_inputs={"constraints": result["constraints"], "profile": result["profile"], "signal_context": result["signal_context"]})
            payload["profile"] = {**payload["profile"], "existing_hardware": ["openmv-h7-plus"], "available_hours": 12}
            changed_response = client.post("/api/analyze", json=payload)
            changed_response.raise_for_status()
            changed = changed_response.json()
            assert changed["change_summary"]["new_search_requests"] == 0
            (folder / "recalculation.json").write_text(json.dumps(changed, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest["recalculation"] = {"new_requests": 0, "changes": changed["change_summary"]["changes"], "claim_status_unchanged": changed["claim_checks"] == result["claim_checks"]}
manifest["successful_question_count"] = sum(c["search_status"] == "ok" and c["result_count"] > 0 for c in manifest["cases"])
(folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"successful_question_count": manifest["successful_question_count"], "requests_this_run": manifest["new_request_count"]}, ensure_ascii=False))
