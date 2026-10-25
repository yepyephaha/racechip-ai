"""Bounded claim audit; a source-domain match never proves a parameter claim."""
import re

from .models import Claim, SignalContext


def audit_claim(claim: Claim | None, signal: SignalContext, catalog: list[dict], source_reviews: list[dict]) -> list[dict]:
    if claim is None:
        return []
    result = {"claim": claim.model_dump(), "status": "insufficient", "reason": "当前字段或说法不在已核对的有界规则内，保留证据不足。",
              "matching_conditions": [], "differing_conditions": [], "evidence_ids": [], "missing": [], "hardware_reproduced": False}
    board = next((h for h in catalog if h["id"] == claim.hardware_id), None)
    if board is None:
        result["missing"] = ["未收录的精确板卡型号"]
        return [result]
    reviewed = [r for r in source_reviews if r.get("status") == "matched" and r.get("hardware_id") == claim.hardware_id]
    needed_field = {"io_tolerance": "io_input_max_v", "lifecycle": "caveats", "algorithm_fps": "engineering_experience", "interface": "interfaces"}[claim.field]
    matched = [r for r in reviewed if needed_field in r.get("fields", [])]
    if not matched:
        result["missing"] = ["本次原文核对未覆盖该精确型号与字段；静态资料/搜索摘要不能代替本次查证"]
        return [result]
    result["evidence_ids"] = [r["evidence_id"] for r in matched]
    result["matching_conditions"] = ["精确型号：" + board["name"], "已匹配原文摘句，未进行硬件实验"]
    text = claim.text
    if claim.field == "io_tolerance":
        max_v = board.get("io_input_max_v")
        voltages = re.findall(r"(\d+(?:\.\d+)?)\s*[vV]", text)
        voltage = signal.voltage_v if signal.voltage_v is not None else float(voltages[0]) if len(voltages) == 1 else None
        positive = bool(re.search(r"可以|能否|安全|兼容|支持|耐受|耐压", text))
        negative = bool(re.search(r"不可以|不能|不安全|不支持|不耐受|不耐压|不兼容|禁止", text))
        if signal.direction != "to_board" or voltage is None or max_v is None or not signal.pin or signal.level_shifter is None:
            result["missing"] = ["需明确输入方向、指定数字信号引脚、电压及是否有转换电路"]
        elif signal.level_shifter:
            result["missing"] = ["需转换器的实际输出、时序和适用引脚证据；不能以供电电压推断"]
        elif voltage > max_v and (positive or negative):
            result.update(status="supported" if negative else "contradicted",
                          reason=f"本型号官方标注 I/O 输入耐受上限 {max_v:g}V；直接输入 {voltage:g}V 超出声明范围，不能按安全兼容接线。")
        elif voltage <= max_v and positive and not negative:
            result.update(status="supported", reason="仅支持输入电压未超厂商标注耐压范围这一子主张；不能据此保证全部引脚、逻辑阈值或完整通信链路。")
        else:
            result["missing"] = ["说法正反或具体电压不明确"]
    elif claim.field == "lifecycle":
        status = board.get("availability_status")
        if status == "discontinued":
            if re.search(r"停止|停产|不再.*生产", text) and not re.search(r"没有停产|未停产|不停产", text):
                result.update(status="supported", reason="官方原文说明停止该版本常规生产，仍可定制批量订单；持有设备不改变生命周期事实。")
            elif re.search(r"仍在.*生产|没有停产|未停产|现货充足", text):
                result.update(status="contradicted", reason="同型号官方原文不支持仍在常规生产；现货数量也未核验。")
        elif status == "backorder" and re.search(r"欠货|预订|backorder", text, re.I):
            result.update(status="supported", reason="本次原文显示可欠货订购；不等于现货或确定交期。")
    elif claim.field == "algorithm_fps":
        if not claim.source_url or claim.source_url.rstrip("/") != matched[0]["url"].rstrip("/"):
            result["missing"] = ["需对应社区经验的原始链接，不能把任意帧率说法套到此帖子"]
        elif claim.sensor.upper() == "OV5640":
            result.update(status="conditions_differ", reason="原帖后续回复限定高 FPS 示例适用于 MT9V034；当前 OV5640、分辨率、AprilTag/传输处理不能直接迁移。没有判定作者造假，也没有本项目实测 FPS。",
                          differing_conditions=["MT9V034 与 OV5640 传感器不同", "采集帧率与带 AprilTag/通信的端到端帧率不同", "固件、曝光、分辨率需一致"])
        else:
            result["missing"] = ["当前传感器、分辨率、曝光、固件和完整处理流程", "独立复现实验"]
    elif claim.field == "interface":
        interfaces = re.findall(r"UART|I2C|SPI|USB|CSI", text.upper())
        if len(set(interfaces)) == 1 and interfaces[0] in board["interfaces"] and not re.search(r"不支持|没有|不能", text):
            result.update(status="supported", reason="对应型号官方原文列出所问接口；引脚复用、协议角色与时序仍需检查。")
    return [result]
