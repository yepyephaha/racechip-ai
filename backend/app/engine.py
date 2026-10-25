from urllib.parse import urlparse

from .models import Constraints
from .parser import CAPABILITY_LABELS


def evaluate_catalog(catalog: list[dict], constraints: Constraints, problem: dict, search: dict | None = None, signal_context: dict | None = None) -> list[dict]:
    candidates = []
    for hardware in catalog:
        checks = []
        evidence = hardware.get("evidence", [])

        def verified(field: str) -> bool:
            return any(e.get("kind") == "official" and e.get("status") == "verified"
                       and (field in e.get("field", "").split(",") or e.get("field") == field)
                       for e in evidence)

        def add(key, expected, actual, status, reason):
            checks.append({"constraint": key, "expected": expected, "actual": actual, "status": status, "reason": reason})

        for key, field, cap, label in (("budget_cny", "price_cny", constraints.budget_cny, "预算上限（板卡，不含完整系统）"),
                                       ("max_power_w", "power_w", constraints.max_power_w, "功耗上限")):
            actual = hardware.get(field)
            if cap is None:
                add(label, None, actual, "not_requested", "未设置此上限")
            elif actual is None or not verified(field):
                add(label, cap, actual, "unknown", "缺少可核验的当前报价/测量条件；不能视为满足")
            else:
                add(label, cap, actual, "pass" if actual <= cap else "fail", f"{actual} {'≤' if actual <= cap else '>'} {cap}")
        actual_interfaces = hardware.get("interfaces", [])
        if constraints.required_interfaces:
            missing = sorted(set(constraints.required_interfaces) - set(actual_interfaces))
            status = "unknown" if not verified("interfaces") or missing else "pass"
            # A public pin list may be incomplete; absence is not proof of incompatibility.
            add("通信接口", constraints.required_interfaces, actual_interfaces, status,
                "官方接口证据覆盖需求" if status == "pass" else "缺少所需接口的已核验证据：" + ", ".join(missing or constraints.required_interfaces))
        else:
            add("通信接口", [], actual_interfaces, "not_requested", "未限定接口")
        voltage = hardware.get("logic_voltage_v")
        if constraints.logic_voltage_v is not None:
            add("逻辑电平 V", constraints.logic_voltage_v, voltage, "unknown",
                "此值仅为板卡输出额定电平；主控电平相等不能证明输入耐压、阈值或双向链路兼容，需明确方向和引脚。")
        else:
            add("逻辑电平 V", None, voltage, "not_requested", "未限定逻辑电平")
        signal = signal_context or {}
        if signal.get("direction") == "to_board" and signal.get("voltage_v") is not None:
            max_v = hardware.get("io_input_max_v")
            if signal.get("level_shifter") is True or max_v is None or not verified("io_input_max_v"):
                status, reason = "unknown", "缺少对应输入耐压或转换电路输出证据，不能推定接线安全。"
            elif signal["voltage_v"] > max_v:
                status, reason = "fail", f"直接输入{signal['voltage_v']:g}V超出官方标注{max_v:g}V耐受范围。"
            elif not signal.get("pin") or signal.get("level_shifter") is None or any(t in signal.get("pin", "").upper() for t in ("ADC", "ANALOG")):
                status, reason = "unknown", "需指定数字信号引脚与转换状态；模拟引脚例外未建模。"
            else:
                status, reason = "pass", "仅输入耐压未超标；逻辑阈值、引脚复用、共地与时序还需按实际链路核对。"
            add("指定方向的输入耐压", signal["voltage_v"], max_v, status, reason)
        elif signal.get("direction") == "from_board":
            add("输出到接收端的阈值", "接收端VIH/VIL及耐压", None, "unknown", "已知板卡输出电平不能替代接收端输入阈值、耐压与具体引脚资料。")
        for task in problem["tasks"]:
            supported = task in hardware.get("capabilities", [])
            trusted = verified("capabilities") or verified(task)
            add(CAPABILITY_LABELS.get(task, task), True, supported if trusted else None,
                "pass" if supported and trusted else "unknown",
                "存在官方示例/文档；未承诺比赛环境帧率" if supported and trusted else "资料未覆盖该任务，需样机实测")
        if not problem["tasks"]:
            add("视觉任务", "明确任务", None, "unknown", "未识别任务，不能生成适用结论")
        if constraints.offline_required:
            offline = "offline_inference" in hardware.get("capabilities", [])
            trusted = verified("offline_inference") or verified("capabilities")
            add("离线运行", True, offline if trusted else None, "pass" if offline and trusted else "unknown",
                "官方文档支持设备本地执行；依赖安装可需联网" if offline and trusted else "缺少离线执行官方证据")
        aliases = {"raspberry-pi-5": "树莓派 Raspberry Pi", "maix-bit-k210": "嘉楠 K210 Maix Bit",
                   "esp32-s3-eye": "乐鑫 ESP32"}.get(hardware["id"], "")
        banned = [b for b in constraints.banned_hardware if b.casefold() in (hardware["name"] + " " + hardware["id"] + " " + hardware["vendor"] + " " + aliases).casefold()]
        add("禁用器件", constraints.banned_hardware, hardware["name"], "fail" if banned else "pass",
            "命中禁止项：" + "、".join(banned) if banned else "未命中用户列出的禁用器件（仍须复核原题）")
        if problem.get("voltage_conflict"):
            add("输入一致性", "正文与表单一致", "电平冲突", "unknown", "请澄清逻辑电平")
        for item in problem.get("unmodeled_constraints", []):
            add("额外硬性条件", item, None, "unknown", "P0 尚未核验该条件，不能据规格直接推定实际性能")
        live_leads = []
        if search is not None and search.get("mode") == "live":
            official_hosts = {urlparse(e.get("url", "")).hostname for e in evidence if e.get("kind") == "official"}
            identity_tokens = {hardware["vendor"].lower(), hardware["name"].lower(), hardware["id"].split("-")[0].lower()}
            for lead in search.get("results", []):
                haystack = (lead.get("title", "") + " " + lead.get("snippet", "") + " " + lead.get("url", "")).lower()
                if any(token and token in haystack for token in identity_tokens):
                    live_leads.append({**lead, "relation": "official_domain_lead" if urlparse(lead["url"]).hostname in official_hosts else "unverified_lead"})
            official_found = any(x["relation"] == "official_domain_lead" for x in live_leads)
            complete = search.get("status") == "ok"
            add("实时检索覆盖", "查询完成且发现对应官方站点线索", len(live_leads),
                "pass" if complete and official_found else "unknown",
                "已检索到候选官方域线索；具体参数仍以固定库逐条官方证据为准" if complete and official_found
                else "实时搜索未完整完成或未找到该候选的官方域线索；不作完整联网推荐")
        verdict = "fail" if any(c["status"] == "fail" for c in checks) else "unknown" if any(c["status"] == "unknown" for c in checks) else "pass"
        task_checks = [c for c in checks if c["constraint"] in CAPABILITY_LABELS.values()]
        fit = round(40 * sum(c["status"] == "pass" for c in task_checks) / max(len(task_checks), 1))
        docs = 4 * min(5, max(1, hardware.get("docs_quality", 1)))
        beginner = 4 * (6 - min(5, max(1, hardware.get("skill_level", 5))))
        trace = min(20, 5 * sum(e.get("kind") == "official" and e.get("status") == "verified" for e in evidence))
        availability = hardware.get("availability_status", "unknown")
        supply_penalty = -10 if availability == "discontinued" else -4 if availability == "backorder" else 0
        breakdown = [
            {"name": "任务资料覆盖", "points": fit, "max_points": 40, "reason": "官方示例覆盖已识别任务的比例"},
            {"name": "文档可用性", "points": docs, "max_points": 20, "reason": "人工维护的文档完整度评分，非客观性能"},
            {"name": "新生上手", "points": beginner, "max_points": 20, "reason": "人工维护的学习难度评分，需结合团队经验"},
            {"name": "证据覆盖", "points": trace, "max_points": 20, "reason": "已核验官方资料条目数，最高 20 分"},
            {"name": "供货风险扣分", "points": supply_penalty, "max_points": 0,
             "reason": "官方停产 -10、欠货订购 -4；未核验库存不等于现货，无额外加分"},
        ]
        candidates.append({"hardware": hardware, "verdict": verdict, "checks": checks,
                           "score": sum(x["points"] for x in breakdown), "score_breakdown": breakdown,
                           "reasons": [c["constraint"] + "：" + c["reason"] for c in checks if c["status"] == "pass"],
                           "risks": list(hardware.get("caveats", [])) + [c["constraint"] + "：" + c["reason"] for c in checks if c["status"] in ("fail", "unknown")],
                           "live_leads": live_leads,
                           "evidence_ids": [e["id"] for e in evidence]})
    return sorted(candidates, key=lambda r: ({"pass": 0, "unknown": 1, "fail": 2}[r["verdict"]], -r["score"], r["hardware"]["id"]))
