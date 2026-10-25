"""Deterministic P0 parser. No LLM calls or claims of full rule understanding."""
import re

from .models import Constraints

CAPABILITY_LABELS = {
    "color_tracking": "颜色识别 / 色块跟踪",
    "apriltag": "AprilTag 定位识别",
    "object_detection": "目标检测",
    "line_tracking": "视觉巡线",
}


def parse_problem(text: str, supplied: Constraints) -> tuple[dict, Constraints, list[str]]:
    requirements = []
    tasks = []
    warnings = []
    patterns = {
        "color_tracking": r"颜色|色块|红色|蓝色|绿色",
        "apriltag": r"AprilTag|April\s*Tag",
        "object_detection": r"目标检测|物体检测|人脸检测|YOLO",
        "line_tracking": r"巡线|循线|寻线|引导线|沿[黑白]线",
    }
    for task, pattern in patterns.items():
        # Ignore an explicitly negated task rather than rewarding it.
        positive_text = re.sub(r"(?:无需|不需要|不用|不要求)[^，。；;\n]{0,12}(?:" + pattern + r")", "", text, flags=re.I)
        match = re.search(pattern, positive_text, re.I)
        if match:
            tasks.append(task)
            requirements.append({"text": CAPABILITY_LABELS[task], "kind": "task", "source_quote": match.group(0)})

    derived: dict = {}
    limit_prefix = r"\s*(?:(?:上限|限制|为|是|约)\s*)?(?:(?:不得超过|不得高于|不超过|不高于|最多|小于等于|≤|<=|[:：])\s*)?"
    budget_match = re.search(r"预算" + limit_prefix + r"[¥￥]?\s*(\d+(?:\.\d+)?)\s*(千|万)?\s*(?:元|人民币|块)?", text)
    power_match = re.search(r"(?:总功耗|功耗|功率)" + limit_prefix + r"(\d+(?:\.\d+)?)\s*(mW|W|瓦)", text, re.I)
    voltage_match = re.search(r"(?:逻辑电平|逻辑电压|IO电平|I/O电平)\s*(?:为|是|[:：])?\s*(\d+(?:\.\d+)?)\s*V", text, re.I)
    for key, match in (("budget_cny", budget_match), ("max_power_w", power_match), ("logic_voltage_v", voltage_match)):
        if match:
            value = float(match.group(1))
            if key == "budget_cny":
                value *= {"千": 1000, "万": 10000}.get(match.group(2), 1)
            if key == "max_power_w" and match.group(2).lower() == "mw":
                value /= 1000
            derived[key] = value
            requirements.append({"text": f"{key}: {value:g}", "kind": "hard", "source_quote": match.group(0)})

    # Only explicit mandatory phrasing; "STM32 有 UART" is not a demand for every board.
    interface_matches = re.finditer(r"(?:必须|要求|需要|使用|通过|采用|仅支持|至少支持)\s*(UART|I2C|I²C|SPI|USB|CSI)", text, re.I)
    derived["required_interfaces"] = []
    for match in interface_matches:
        derived["required_interfaces"].append(match.group(1).upper().replace("I²C", "I2C"))
        requirements.append({"text": f"接口 {match.group(1)}", "kind": "hard", "source_quote": match.group(0)})
    derived["offline_required"] = bool(re.search(r"离线|不(?:允许|能|可)(?:使用)?(?:联网|网络)|禁止联网", text)) and not bool(re.search(r"不要求离线|无需离线", text))

    merged = supplied.model_dump()
    for key in ("budget_cny", "max_power_w"):
        if key in derived:
            if merged[key] is not None and merged[key] != derived[key]:
                warnings.append(f"正文与表单 {key} 不一致，采用更严格上限；请核对原题。")
            merged[key] = min(derived[key], merged[key]) if merged[key] is not None else derived[key]
    voltage_conflict = False
    if "logic_voltage_v" in derived:
        voltage_conflict = merged["logic_voltage_v"] is not None and merged["logic_voltage_v"] != derived["logic_voltage_v"]
        if voltage_conflict:
            warnings.append("正文与表单逻辑电平冲突，所有候选须人工澄清后才能通过。")
        else:
            merged["logic_voltage_v"] = derived["logic_voltage_v"]
    merged["required_interfaces"] = list(dict.fromkeys(merged["required_interfaces"] + derived["required_interfaces"]))
    merged["offline_required"] = merged["offline_required"] or derived["offline_required"]
    for ban_match in re.finditer(r"(?:禁止使用|禁用|不允许使用)\s*([^，。；;\n]{1,60})", text):
        ban = ban_match.group(1).strip()
        if not re.search(r"联网|网络", ban):
            merged["banned_hardware"].extend(v.strip() for v in re.split(r"[、,]|以及|和", ban) if v.strip())
        requirements.append({"text": f"禁止：{ban}", "kind": "hard", "source_quote": ban_match.group(0)})

    # P0 cannot verify application-level latency/FPS/dimensions/total-system metrics.
    unmodeled = []
    for segment in re.split(r"[。；;\n]", text):
        unsupported = re.search(r"\d+(?:\.\d+)?\s*(?:fps|帧|ms|毫秒|厘米|cm|mm|毫米|克|kg|g\b)|必须国产|必须开源|不能使用Linux|禁止Linux|禁止使用Linux", segment, re.I)
        full_system = re.search(r"完整|整机|总预算|全套|含摄像头", segment) and re.search(r"预算|功耗|价格|成本", segment)
        if unsupported or full_system:
            unmodeled.append(segment.strip())
            requirements.append({"text": "需额外验证：" + segment.strip(), "kind": "hard_unmodeled", "source_quote": segment.strip()})
    ambiguities = ["P0 使用关键词与单位规则解析；原题限定器件、测量条件、评分细则须逐条人工复核。"]
    if not tasks:
        ambiguities.append("未识别到支持的视觉任务，无法判定任务适配。请明确颜色、巡线、AprilTag 或目标检测。")
    if unmodeled:
        ambiguities.append("存在 P0 尚不能自动核验的性能或限制条件；候选标记待核验。")
    if merged["budget_cny"] is not None:
        ambiguities.append("预算按候选视觉板卡判断；完整机器人还需摄像头、主控、供电、驱动及运费，P0 不生成完整 BOM。")
    title = " / ".join(CAPABILITY_LABELS[t] for t in tasks) + " · 选型调查" if tasks else "未识别视觉任务 · 需要澄清"
    return ({"title": title, "tasks": tasks, "requirements": requirements,
             "ambiguities": ambiguities, "parser": "deterministic-rules-v1", "unmodeled_constraints": unmodeled,
             "voltage_conflict": voltage_conflict}, Constraints(**merged), warnings)
