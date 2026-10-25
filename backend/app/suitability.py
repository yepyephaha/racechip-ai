"""User-reported fit rules, separated from hardware facts and technical verdicts."""
from .models import Profile


def apply_profile(recommendations: list[dict], profile: Profile, only_existing: bool) -> list[dict]:
    for item in recommendations:
        hw = item["hardware"]
        risks, advantages, missing, adjustment = [], [], [], 0
        owned = hw["id"] in profile.existing_hardware
        if owned:
            advantages.append("用户自述已持有此板，采购等待风险降低；不等于实测可用。")
            adjustment += 6
        elif hw.get("availability_status") in ("discontinued", "backorder"):
            risks.append("需要新购，停产/欠货与交期不明会影响交付。")
            adjustment -= 6
        if hw["id"] == "raspberry-pi-5" and profile.linux_experience == "none":
            risks.append("用户自述无 Linux 经验，需先验证系统、相机和依赖安装。")
            adjustment -= 5
            if profile.available_hours is not None and profile.available_hours < 8:
                risks.append("剩余时间小于产品规则阈值8小时，先做工具链冒烟；这不是实测工时预测。")
                adjustment -= 5
        if profile.programming == "c" and hw["vendor"] in ("OpenMV", "Sipeed"):
            risks.append("仅有 C 基础，需验证 MicroPython/MaixPy 的示例修改能力。")
            adjustment -= 3
        if profile.available_hours is None:
            missing.append("尚未填写可投入小时，未自动假定24小时")
        if not profile.tools:
            missing.append("调试工具未知；不能声称已测电平和时延")
        if only_existing:
            status = "pass" if owned else "fail"
            item["checks"].append({"constraint": "仅用现有器材", "expected": profile.existing_hardware, "actual": hw["id"], "status": status,
                                   "reason": "用户明确限制为现有器材；自述持有仍需核验设备状态" if owned else "未列入用户自述现有器材范围"})
            if not owned:
                item["verdict"] = "fail"
                item["risks"].append("违反仅用现有器材的硬限制")
        item["suitability"] = {"source": "user_reported", "owned": owned, "adjustment": adjustment,
                               "risks": risks, "advantages": advantages, "missing_inputs": missing,
                               "rule_note": "适配只改变同技术状态内排序，不修改硬件事实或消除fail/unknown。"}
        item["ranking_score"] = item["score"] + adjustment
    return sorted(recommendations, key=lambda r: ({"pass": 0, "unknown": 1, "fail": 2}[r["verdict"]], -r["ranking_score"], r["hardware"]["id"]))


def verification_actions(board: dict) -> list[dict]:
    url = next((e["url"] for e in board["evidence"] if e["kind"] == "official"), "")
    return [{"hardware_id": board["id"], "title": "先核对电气条件，再运行最小视觉示例", "prerequisites": ["精确板型与修订版", "与信号方向对应的引脚图", "可用电平转换/测量工具"],
             "steps": ["核对供电输入、信号输出和输入耐压；方向或引脚不明时不直接接线。", "先用厂商示例读取一帧图像，再启用所需算法。", "记录传感器、固件、分辨率、曝光和目标条件，测完整算法与通信链路。"],
             "pass_condition": "电气条件有对应原文，示例可运行，完整链路达到本人赛题的已录入阈值。", "failure_next_step": "停止不兼容接线；补转换电路或更换候选，降低分辨率后重新测量而非沿用他人FPS。",
             "source_url": url, "suggested_timebox_minutes": 30, "timebox_note": "建议验证时间预算，不是交付耗时保证。", "executed": False}]
