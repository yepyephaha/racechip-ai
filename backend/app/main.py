import json
import copy
from collections import OrderedDict
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import evaluate_catalog
from .models import AnalyzeRequest
from .parser import parse_problem
from .search import build_queries, configured, run_search
from .auth import auth_mode
from .claim_checks import audit_claim
from .source_review import collect_reviews
from .suitability import apply_profile, verification_actions
from .hardware_api import router as hardware_router
from .decision import settings as decision_settings
from .procurement_api import router as procurement_router
from .fact_check import router as fact_check_router, monitor_router
from .design_runs import router as design_runs_router

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.3.0"
CACHE: OrderedDict = OrderedDict()
app = FastAPI(title="赛芯智选 RaceChip AI", version=VERSION,
              description="P0 证据选型工作台。规则解析 + 三态约束 + SearchPro 真实/Mock 显式模式。")
app.include_router(hardware_router)
app.include_router(procurement_router)
app.include_router(fact_check_router)
app.include_router(monitor_router)
app.include_router(design_runs_router)


def load_data(name: str):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8-sig"))


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION, "search_mode": "live" if configured() else "mock",
            "search_configured": configured(), "auth_mode": auth_mode(), "decision":decision_settings()}


@app.get("/api/scenarios")
def scenarios():
    return load_data("investigations.json") + load_data("scenarios.json")


@app.get("/api/demo-cases")
def demo_cases():
    folder = ROOT / "artifacts" / "live"
    results = []
    for path in sorted(folder.glob("case-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("mode") == "live" and data.get("search", {}).get("status") == "ok":
            results.append({"id": path.stem, "title": data["problem"]["title"], "created_at": data["created_at"], "query_count": data["search"]["request_count"]})
    return results


@app.get("/api/demo-cases/{name}")
def demo_case(name: str):
    if not re.fullmatch(r"case-[a-z0-9-]{1,60}", name):
        raise HTTPException(404, "无此实录")
    path = ROOT / "artifacts" / "live" / (name + ".json")
    if not path.is_file():
        raise HTTPException(404, "无此实录")
    result = json.loads(path.read_text(encoding="utf-8"))
    result["playback"] = True
    CACHE[result["case_id"]] = copy.deepcopy(result)
    return result


@app.get("/api/catalog")
def catalog():
    return load_data("catalog.json")


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    try:
        problem, constraints, warnings = parse_problem(request.problem_text, request.constraints)
    except ValidationError:
        raise HTTPException(status_code=422, detail="正文中识别到的数值超出支持范围，请核对单位及数值。") from None
    records = load_data("catalog.json")
    target = request.claim.hardware_id if request.claim else None
    claim_data = request.claim.model_dump() if request.claim else None
    if request.reuse_case_id:
        cached = CACHE.get(request.reuse_case_id)
        if not cached or cached["input_text"] != request.problem_text or cached.get("claim") != claim_data or cached["mode"] != request.search_mode:
            raise HTTPException(422, "原调查已过期或任务/主张/模式已改变，请重新检索。")
        search, source_reviews = copy.deepcopy(cached["search"]), copy.deepcopy(cached["source_reviews"])
        search["reused_from_case_id"] = cached["case_id"]
        search["original_created_at"] = cached["created_at"]
        search["new_request_count"] = 0
    else:
        search = await run_search(request.search_mode, build_queries(problem, constraints.model_dump(), claim_data))
        search["new_request_count"] = search["request_count"]
        source_reviews = await collect_reviews(records, target) if request.search_mode == "live" and search["status"] == "ok" else []
    recommendations = evaluate_catalog(records, constraints, problem, search, request.signal_context.model_dump())
    recommendations = apply_profile(recommendations, request.profile, constraints.only_existing_hardware)
    claim_checks = audit_claim(request.claim, request.signal_context, records, source_reviews)
    passed = sum(item["verdict"] == "pass" for item in recommendations)
    unknown = sum(item["verdict"] == "unknown" for item in recommendations)
    evidence = list({item["id"]: item for hw in records for item in hw["evidence"]}.values())
    warnings.extend(search["warnings"])
    warnings.extend(["评分为人工权重的解释性排序，不是成功概率、竞赛成绩或实时性能评测。",
                     "推荐仅覆盖已建库的视觉板卡；原题合规性、供货状态、完整系统成本与样机性能需用户核验。"])
    if search["error"]:
        warnings.append("实时检索未完成；下方仅展示固定硬件库的约束评估，不能视为完整联网推荐。")
    result = {"case_id": str(uuid4()), "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "mode": request.search_mode, "input_text": request.problem_text, "problem": problem, "constraints": constraints.model_dump(),
              "search": search, "evidence": evidence, "recommendations": recommendations,
              "claim": claim_data, "claim_checks": claim_checks, "source_reviews": source_reviews,
              "profile": request.profile.model_dump(), "signal_context": request.signal_context.model_dump(),
              "suitability": [{"hardware_id": c["hardware"]["id"], **c["suitability"]} for c in recommendations],
              "verification_actions": [a for h in records if not target or h["id"] == target for a in verification_actions(h)],
              "summary": f"{passed} 项通过已录入条件，{unknown} 项待核验，{len(records) - passed - unknown} 项存在冲突。"
                         + (" 可优先验证通过项的样机。" if passed else " 当前没有可无条件推荐的候选，请补充证据或澄清条件。"),
              "warnings": warnings}
    previous = request.previous_inputs.model_dump() if request.previous_inputs else None
    current = {"constraints": constraints.model_dump(), "profile": request.profile.model_dump(), "signal_context": request.signal_context.model_dump()}
    changes = [{"field": section + "." + key, "before": previous[section].get(key), "after": value}
               for section in current for key, value in current[section].items()
               if previous and previous[section].get(key) != value]
    result["change_summary"] = {"changes": changes, "reason": "未提供上次输入，无前后比较。" if not previous else "未检测到输入变化。" if not changes else "按新输入重算；技术证据不因技能或时间变化而改变，适配只影响同状态排序。",
                                "reused_evidence": bool(request.reuse_case_id), "new_search_requests": search["new_request_count"]}
    result["follow_up_questions"] = ([{"question": "信号由谁发向哪块板、具体引脚和转换电路是什么？", "reason": "方向/耐压影响安全接线与电平判断"}] if constraints.logic_voltage_v and request.signal_context.direction == "unspecified" else [])
    if request.profile.available_hours is None:
        result["follow_up_questions"].append({"question": "剩余可投入多少小时，是否已持有目标板卡？", "reason": "影响采购与工具链验证风险，不能改变硬件规格"})
    result["follow_up_questions"] = result["follow_up_questions"][:2]
    CACHE[result["case_id"]] = copy.deepcopy(result)
    while len(CACHE) > 20:
        CACHE.popitem(last=False)
    return result


@app.get("/api/cases/{case_id}")
def saved_case(case_id: str):
    result = CACHE.get(case_id)
    if not result:
        raise HTTPException(404, "本进程中没有此调查记录；请导入下载报告或重新查询。")
    return result


# Single-origin production preview: API and built Vite files share localhost:8000.
# Mount assets only; unknown API paths keep a proper 404 instead of HTML.
DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/")
def index():
    if (DIST / "index.html").is_file():
        return FileResponse(DIST / "index.html")
    return JSONResponse({"message": "请先构建 frontend，或使用 Vite 开发服务。", "docs": "/docs"})
