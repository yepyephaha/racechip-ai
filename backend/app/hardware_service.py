"""General hardware workflow: bounded rules, explicit provenance, no vendor lock-in."""
import csv
import io
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .hardware_models import HardwareProject, DialogueRequest, CustomPart, BomLine

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = {"embedded":"嵌入式与控制", "iot":"物联网", "power":"电源与功率", "measurement":"仪器与采集", "motion":"电机与运动", "fpga":"FPGA / DSP", "robotics":"机器人", "custom":"通用硬件"}
TEMPLATES = {
    "iot": ["感知与采集", "主控与通信", "供电与保护"],
    "power": ["输入与保护", "功率变换", "反馈与采样", "控制与散热"],
    "measurement": ["输入前端与保护", "ADC / 采样", "时钟与主控", "通信与显示"],
    "motion": ["控制器", "驱动与保护", "电机与机构", "位置反馈", "供电"],
    "fpga": ["FPGA / DSP", "时钟与复位", "电源时序", "外设与下载"],
    "robotics": ["感知", "计算与控制", "执行机构", "供电与通信"],
    "embedded": ["主控", "输入与输出", "电源与保护"],
    "custom": ["输入与功能", "处理与控制", "输出与执行", "供电与接口"],
}


def reference_catalog():
    return json.loads((ROOT / "data/hardware_catalog.json").read_text(encoding="utf-8"))


def resolve_parts(project: HardwareProject):
    parts = {p["id"]: p for p in reference_catalog()}
    for p in project.custom_parts:
        if p.id in parts:
            raise ValueError("自定义ID不能覆盖已核验参考库")
        parts[p.id] = {**p.model_dump(), "mpn":p.name, "capabilities":[], "notes":[p.notes], "accessed_at":None,
                       "facts":{k:{"value":v.get("value") if isinstance(v,dict) else v,"unit":v.get("unit","") if isinstance(v,dict) else "", "source_url":p.source_url,"status":"user_asserted","scope":"用户输入，未自动核对原文"} for k,v in p.facts.items()}}
    missing = [b.part_id for b in project.bom if b.part_id not in parts]
    if missing:
        raise ValueError("BOM包含未录入型号：" + ", ".join(missing))
    return parts


def detect_domain(text: str):
    patterns = [("power",r"稳压|降压|升压|电源|充电|逆变|buck|boost"),("fpga",r"FPGA|DSP|Verilog|高速逻辑"),("robotics",r"机器人|机械臂|巡线|循线|循迹|小车"),("motion",r"电机|伺服|步进|运动控制"),("iot",r"物联网|无线|温湿度|LoRa|Wi.?Fi|环境监测"),("measurement",r"采集|示波器|测量|仪器|ADC"),("embedded",r"MCU|单片机|主控|嵌入式")]
    return next((domain for domain,pat in patterns if re.search(pat,text,re.I)), "custom")


def dialogue(request: DialogueRequest):
    project = request.project.model_copy(deep=True)
    message = request.message.strip()
    if request.pending_key:
        project.requirements[request.pending_key] = message
        if request.pending_key == "budget":
            m = re.search(r"(\d+(?:\.\d+)?)",message)
            if m: project.budget_cny = float(m.group(1))
    else:
        project.description = (project.description + "\n" + message).strip()
        if project.name == "未命名硬件项目": project.name = message[:35]
    if project.domain == "auto": project.domain = detect_domain(project.description)
    if request.pending_key == "purpose" and project.domain == "custom": project.domain=detect_domain(message)
    text = project.description + "\n" + "\n".join(str(h.get("text","")) for h in request.history if h.get("role")=="user") + "\n" + message
    if re.search(r"电池",message): project.requirements["power_source"]="电池供电"
    elif re.search(r"USB供电|USB 供电",message,re.I): project.requirements["power_source"]="USB供电"
    elif re.search(r"电池",text): project.requirements.setdefault("power_source","电池供电")
    elif re.search(r"USB供电|USB 供电",text,re.I): project.requirements.setdefault("power_source","USB供电")
    if re.search(r"Wi.?Fi",text,re.I): project.requirements.setdefault("connectivity","Wi-Fi")
    if re.search(r"LoRa",text,re.I): project.requirements.setdefault("connectivity","LoRa")
    if re.search(r"红外.*(?:循迹|巡线|循线)|(?:循迹|巡线|循线).*红外",text): project.requirements.setdefault("tracking_method","红外循迹")
    if re.search(r"视觉.*(?:循迹|巡线|循线)|(?:循迹|巡线|循线).*视觉",text): project.requirements.setdefault("tracking_method","视觉循迹")
    power_match=re.search(r"\d+(?:\.\d+)?\s*V\s*(?:转|到|->)\s*\d+(?:\.\d+)?\s*V(?:[^。\n]{0,30}\d+(?:\.\d+)?\s*A)?",text,re.I)
    if power_match: project.requirements.setdefault("power_io",power_match.group(0))
    resource_match=re.search(r"(?:会|熟悉|已有|具备|只有)[^。\n]{0,35}(?:基础|万用表|逻辑分析仪|示波器|开发板|经验)",text)
    if resource_match: project.requirements.setdefault("resources",resource_match.group(0))
    matches=list(re.finditer(r"预算\s*(?:改为|改成|不超过|约|为|[:：])?\s*(\d+(?:\.\d+)?)",text))
    if matches: project.budget_cny = float(matches[-1].group(1))
    if re.search(r"预算.*(?:不限|不设上限)|暂不设上限",message): project.budget_cny=None;project.requirements['budget']='暂不设上限'
    if re.search(r"改[用为成].*视觉",message): project.requirements['tracking_method']='视觉循迹'
    if re.search(r"改[用为成].*红外",message): project.requirements['tracking_method']='红外循迹'
    questions = []
    if project.domain == "custom" and "purpose" not in project.requirements:
        questions.append(("purpose","最希望这套硬件完成哪一个具体动作或测量？",["采集传感器数据","控制电机或执行器","做电源变换","自定义目标"],"先确定功能，才能选择主控、功率或采集架构。"))
    if project.domain == "power":
        questions += [("power_io","电源输入范围、目标输出和负载电流分别是多少？",["12V转5V，负载待确认","电池输入，输出待确认","我还不清楚"],"这会改变拓扑、器件耐压和散热核验范围。")]
    else:
        questions += [("power_source","设备准备怎样供电？",["USB供电","电池供电","外部直流电源","尚未确定"],"供电会影响功耗、稳压和接口条件。")]
    if project.domain == "iot":
        questions += [("connectivity","数据需要怎样传出去，距离大约多远？",["近距离Wi-Fi","远距离LoRa","先本地存储","尚未确定"],"通信范围会改变无线模块和电源预算。")]
    if project.domain in ("measurement","fpga"):
        questions += [("performance","采样率、带宽或处理时延最关键的指标是什么？",["先低速原型","已有明确指标，输入数值","尚未确定"],"没有时序目标，不能保证ADC、时钟和处理器满足要求。")]
    if project.domain in ("motion","robotics"):
        if re.search(r"循迹|巡线|循线",text):
            questions += [("tracking_method","循迹需要识别怎样的路线或标记？",["简单黑白线，先比较红外阵列","需要颜色/图形，考虑视觉","还不清楚，我先描述场地"],"传感器路线会改变计算模块、成本和调试需求，不预设必须使用摄像头。")]
        questions += [("load","执行机构的负载、电压和速度/扭矩要求是什么？",["已有电机，稍后录入型号","先做小型低速原型","尚未确定"],"负载决定驱动、电源与机械验证，不能只按主控选择。")]
    if project.budget_cny is None:
        questions += [("budget","整个原型的预算上限是多少？",["300元","1000元","暂不设上限"],"按完整BOM核算，不能用裸芯片价格代表整套方案。")]
    questions += [("resources","你已有器材、工具或开发经验有哪些？",["只有C基础和万用表","有Python基础和开发板","有Linux/FPGA经验","从零开始"],"只调整实现与验证风险，不修改硬件事实。")]
    question = next((q for q in questions if q[0] not in project.requirements), None)
    history = [*request.history, {"role":"user","text":message}]
    needed_modules=[]
    if project.domain in ('robotics','motion'):
        sensor='红外循迹阵列' if '红外' in project.requirements.get('tracking_method','') else '视觉/位置感知模块（路线待选）'
        needed_modules=[sensor,'主控与通信','电机驱动（按堵转电流核对）','电机/减速器与反馈','电池/稳压/保护','底盘、轮胎与连接件']
    else:
        needed_modules=TEMPLATES.get(project.domain,TEMPLATES['custom'])
    if question:
        key,prompt,choices,reason=question
        assistant = {"role":"assistant","text":prompt,"reason":reason,"question_key":key,"choices":choices}
    else:
        assistant = {"role":"assistant","text":"已有条件足以建立可编辑草案。先拆成："+'、'.join(needed_modules)+"。下一步逐模块选入精确型号，核对连接与价格；未知条件进入验证清单。","reason":"功能模块不是已完成的BOM，仍需确认型号和工况。","question_key":None,"choices":[]}
    history.append(assistant)
    starts={"iot":["esp32-devkitc-v4","bosch-bme280"],"power":["ti-lm2596-evm","ti-lm2596-adj"],"embedded":["arduino-uno-r3","esp32-devkitc-v4"],"measurement":["arduino-uno-r3","bosch-bme280"],"robotics":["openmv-rt1062","esp32-devkitc-v4"],"motion":["esp32-devkitc-v4"],"fpga":[],"custom":[]}
    candidates=[{"part_id":p["id"],"name":p["name"],"category":p["category"],"reason":"按当前功能方向提供有原文出处的比较起点；尚未证明满足所有性能、供电与连接条件。"} for p in reference_catalog() if p["id"] in starts.get(project.domain,[])] if question is None else []
    if project.requirements.get("connectivity","").lower().find("lora")>=0:
        candidates=[c for c in candidates if c["part_id"]!="esp32-devkitc-v4"]
    if '红外' in project.requirements.get('tracking_method',''):
        candidates=[c for c in candidates if c['category']!='vision']
    return {"project":project.model_dump(mode="json"),"history":history[-48:],"assistant":assistant,"ready":question is None,"draft_blocks":TEMPLATES.get(project.domain,TEMPLATES["custom"]),"needed_modules":needed_modules if question is None else [],"candidate_parts":candidates,"candidate_scope":"有限参考库比较起点；LoRa等未覆盖能力需用元宝发现精确型号，不能把Wi-Fi模块当LoRa。","method":"progressive_rules_with_explicit_unknowns"}


def numeric_fact(part, key):
    fact = part.get("facts",{}).get(key,{})
    value = fact.get("value")
    if not isinstance(value,(int,float)) or isinstance(value,bool) or fact.get("status") != "source_checked": return None
    unit=fact.get("unit","")
    expected="V" if key.endswith("_v") else "A" if key.endswith("_a") else "W" if key.endswith("_w") else unit
    if unit in ("mV","mA","mW") and unit[1:]==expected: return value/1000
    if unit==expected and unit in ("V","A","W",""): return float(value)
    return None


def check_connection(edge, refs, parts):
    left,right=parts[refs[edge.from_ref].part_id],parts[refs[edge.to_ref].part_id]
    checks=[]
    def add(name,status,reason,fields):
        evidence=[{"part_id":p["id"],"field":field,"source_url":p.get("facts",{}).get(field,{}).get("source_url"),"status":p.get("facts",{}).get(field,{}).get("status","unknown")} for p,field in fields]
        checks.append({"id":f"{edge.from_ref}-{edge.to_ref}-{len(checks)}","name":name,"status":status,"reason":reason,"from_ref":edge.from_ref,"to_ref":edge.to_ref,"evidence":evidence})
    if edge.kind == "power":
        out=numeric_fact(left,"output_voltage_v")
        if edge.voltage_v is not None: out=edge.voltage_v
        low,high=numeric_fact(right,"supply_min_v"),numeric_fact(right,"supply_max_v")
        if out is None or low is None or high is None: status,reason="unknown","缺少明确输出与目标供电范围；不能把GPIO电平当作供电。"
        elif low<=out<=high: status,reason="pass",f"按所填连接，{out:g}V在{low:g}–{high:g}V范围内；仍需共地、纹波与时序验证。"
        else: status,reason="fail",f"{out:g}V超出接收器件{low:g}–{high:g}V供电范围。"
        add("供电范围",status,reason,[(left,"output_voltage_v"),(right,"supply_min_v"),(right,"supply_max_v")])
        capacity=numeric_fact(left,"output_current_a")
        if edge.load_a is not None:
            add("负载电流","unknown" if capacity is None else "pass" if edge.load_a<=capacity else "fail","需要持续输出、散热与工况证据；最大额定值不能当成整机保证。" if capacity is None else "仅在记录工况与所填负载条件下比较。",[(left,"output_current_a")])
    elif edge.kind == "signal":
        out=edge.voltage_v if edge.voltage_v is not None else numeric_fact(left,"logic_voltage_v")
        high=numeric_fact(right,"io_input_max_v")
        if out is not None and high is not None and out>high: status,reason="fail",f"输入{out:g}V高于厂商声明{high:g}V耐受范围。"
        else: status,reason="unknown","耐压未超标不等于VIH/VIL、方向、引脚和时序完整兼容，请补接收阈值。"
        add("信号电气",status,reason,[(left,"logic_voltage_v"),(right,"io_input_max_v")])
    elif edge.kind == "protocol":
        a,b=left.get("facts",{}).get("interfaces",{}),right.get("facts",{}).get("interfaces",{})
        protocol=edge.protocol.upper()
        supported=protocol and all(x.get("status")=="source_checked" and protocol in x.get("value",[]) for x in (a,b))
        add("协议与引脚","pass" if supported else "unknown","两端已录入接口覆盖此协议；角色、引脚复用和速率仍需核对。" if supported else "缺少两端同协议的已核验证据；没有写出不等于绝对不支持。",[(left,"interfaces"),(right,"interfaces")])
    else:
        key="mount_pattern" if edge.kind=="mechanical" else "software_compat"
        a,b=left.get("facts",{}).get(key,{}),right.get("facts",{}).get(key,{})
        av,bv=a.get("value"),b.get("value")
        trusted=all(v.get("status")=="source_checked" for v in (a,b))
        known=av is not None and bv is not None
        if edge.kind=="mechanical":
            matches=known and av==bv
            reason="按直接装配比较安装孔型；转接件需另录入。" if trusted and known else "需精确安装孔型/单位与来源，不能仅按器件名称推定装配。"
        else:
            av=av if isinstance(av,list) else [av] if av is not None else []
            bv=bv if isinstance(bv,list) else [bv] if bv is not None else []
            matches=bool(set(av)&set(bv))
            reason="仅比较已声明OS/ROS/驱动兼容版本交集，具体功能仍需联调。" if trusted and known else "需两端OS/ROS/驱动版本证据；同名接口不代表软件可运行。"
        status="pass" if trusted and known and matches else "fail" if trusted and known else "unknown"
        if known and not trusted:
            reason += " 用户所填条件"+("一致，但仍待原文核对。" if matches else "存在差异，应先核对，不能据此宣布兼容。")
        add("机械安装孔型" if edge.kind=="mechanical" else "软件版本交集",status,reason,[(left,key),(right,key)])
    return checks


def review_project(project: HardwareProject, previous: HardwareProject | None = None):
    parts=resolve_parts(project)
    refs={line.ref:line for line in project.bom}
    checks=[c for edge in project.connections for c in check_connection(edge,refs,parts)]
    lines=[]
    for line in project.bom:
        part=parts[line.part_id]
        dated=line.quote_at is not None and abs((datetime.now(timezone.utc)-line.quote_at.replace(tzinfo=line.quote_at.tzinfo or timezone.utc)).total_seconds())<=7*86400
        quoted=line.unit_price_cny is not None
        attributed=quoted and bool(line.quote_source) and dated and line.quote_kind=="user_quote"
        lines.append({**line.model_dump(mode="json"),"part":part,"line_total_cny":round(line.quantity*line.unit_price_cny,4) if quoted else None,
                      "quote_status":"user_quote_current" if attributed else "needs_confirmation" if quoted else "missing","is_market_verified":False})
    subtotal=round(sum(line["line_total_cny"] or 0 for line in lines),4)
    unknown_cost=sum(line["line_total_cny"] is None for line in lines)
    total=subtotal if lines and not unknown_cost else None
    budget_status="not_requested" if project.budget_cny is None else "fail" if subtotal>project.budget_cny else "unknown" if not lines or any(line["quote_status"]!="user_quote_current" for line in lines) else "pass"
    budget={"known_subtotal_cny":subtotal,"total_cny":total,"missing_price_lines":unknown_cost,"status":budget_status,"limit_cny":project.budget_cny,"scope":"按所填报价计算；不含未录入配件、运费、税费。未自动验证商家报价。"}
    clarifications=[]
    if not lines: clarifications.append("先选择精确型号或导入BOM，不能把功能块草案当完整器件方案。")
    if lines and not project.connections: clarifications.append("尚未录入连接关系，不能得出整机兼容结论。")
    if unknown_cost: clarifications.append(f"{unknown_cost}行价格未知；可使用元宝检索商家来源并核对套装后录入。")
    if not project.requirements.get("resources"): clarifications.append("实现经验与调试工具未确认，验证任务仍需结合实际资源。")
    failures=[c for c in checks if c["status"]=="fail"]
    unknowns=[c for c in checks if c["status"]=="unknown"]
    verdict="fail" if failures or budget_status=="fail" else "unknown" if not lines or not project.connections or unknowns or budget_status=="unknown" else "pass"
    actions=[]
    for c in failures+unknowns:
        actions.append({"priority":"先解决冲突" if c["status"]=="fail" else "补证据后验证","title":f"{c['from_ref']} → {c['to_ref']}：{c['name']}","reason":c["reason"],"affected_refs":[c["from_ref"],c["to_ref"]],"steps":["按精确板型、引脚及工作条件打开对应原文。","在上电或换件前核对该项，再做最小负载验证。"],"pass_condition":"原文范围覆盖本连接，且按目标工况实际测量通过。","executed":False,"evidence":c["evidence"]})
    if unknown_cost: actions.append({"priority":"补采购依据","title":"核对缺失报价、SKU与数量梯度","reason":"芯片价、模块起价和套装总价不能混用。","affected_refs":[l["ref"] for l in lines if l["line_total_cny"] is None],"steps":["用元宝搜索精确型号和平台价格。","打开原商品页确认规格、套装、库存、含税与运费。"],"pass_condition":"每行报价有时间和SKU条件，采购前再次确认。","executed":False,"evidence":[]})
    changes=[]
    if previous:
        old={l.ref:l for l in previous.bom}
        old_parts=resolve_parts(previous)
        for line in project.bom:
            before=old.get(line.ref)
            for field in ("part_id","quantity","unit_price_cny"):
                if before is None or getattr(before,field)!=getattr(line,field):
                    affected=[c["id"] for c in checks if line.ref in (c["from_ref"],c["to_ref"])]
                    changes.append({"ref":line.ref,"field":field,"before":getattr(before,field) if before else None,"after":getattr(line,field),"affected_checks":affected,"effect":"型号变更需重查相邻连接和引用；数量/报价变更会重新核算BOM。"})
            if before and before.part_id==line.part_id:
                old_facts=old_parts[line.part_id].get("facts",{});new_facts=parts[line.part_id].get("facts",{})
                for key in set(old_facts)|set(new_facts):
                    if old_facts.get(key)!=new_facts.get(key):
                        changes.append({"ref":line.ref,"field":"parameter:"+key,"before":old_facts.get(key,{}).get("value"),"after":new_facts.get(key,{}).get("value"),"affected_checks":[c["id"] for c in checks if line.ref in (c["from_ref"],c["to_ref"])],"effect":"参数或来源变化已传播到相邻连接；用户自述仍待原文核对。"})
        for removed in set(old)-set(refs): changes.append({"ref":removed,"field":"removed","before":old[removed].part_id,"after":None,"affected_checks":[],"effect":"器件已移出BOM；相关功能和连接需重新确认。"})
        if previous.budget_cny!=project.budget_cny:
            changes.append({"ref":"项目","field":"budget","before":previous.budget_cny,"after":project.budget_cny,"affected_checks":[],"effect":"重新将当前BOM所填报价与新预算比较，报价缺口没有被消除。"})
        if previous.connections!=project.connections:
            changes.append({"ref":"连接","field":"connections","before":len(previous.connections),"after":len(project.connections),"affected_checks":[c["id"] for c in checks],"effect":"连接关系/设计条件变化，重新执行电气、协议、机械或软件检查。"})
    return {"review_id":str(uuid4()),"created_at":datetime.now(timezone.utc).isoformat(),"project":project.model_dump(mode="json"),"domain_label":DOMAINS.get(project.domain,DOMAINS["custom"]),"architecture":{"blocks":[{"ref":l["ref"],"label":l["part"]["name"],"category":l["part"]["category"]} for l in lines],"connections":[e.model_dump() for e in project.connections],"draft_function_blocks":TEMPLATES.get(project.domain,TEMPLATES["custom"]),"status":"editable_system_draft_not_native_schematic"},"bom":lines,"budget":budget,"checks":checks,"verdict":verdict,"clarifications":clarifications,"verification_actions":actions,"change_impact":changes,"evidence_links":[{"check_id":c["id"],"affected_refs":[c["from_ref"],c["to_ref"]],"sources":c["evidence"]} for c in checks],"limitations":["通过只覆盖已建模连接，不能作为整机电气/机械/EMC/量产认证。","参考库为有限核验样例；自定义器件与任意硬件项目可录入，但未知参数不会自动变成已核实。","结构草案与交接网表不等于原生EDA原理图、PCB或可直接生产文件。"]}


def import_bom(csv_text: str):
    reader=csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    known=reference_catalog();lines=[];custom=[];errors=[]
    for i,row in enumerate(reader,2):
        if i>82: raise ValueError("最多导入80行")
        try:
            model=(row.get("mpn") or row.get("型号") or "").strip()
            if not model: raise ValueError("缺少mpn/型号")
            found=next((p for p in known if model.casefold() in (p["mpn"].casefold(),p["name"].casefold(),p["id"].casefold())),None)
            pid=found["id"] if found else "import-"+str(uuid4())[:8]
            quantity=int(row.get("quantity") or row.get("数量") or 1)
            if quantity<1: raise ValueError("数量必须大于0")
            price=row.get("unit_price_cny") or row.get("单价")
            line=BomLine(ref=row.get("ref") or row.get("位号") or f"U{i-1}",part_id=pid,quantity=quantity,unit_price_cny=float(price) if price else None,quote_source=row.get("source", ""),quote_kind="unknown")
            if any(existing['ref']==line.ref for existing in lines):raise ValueError('位号重复')
            lines.append(line.model_dump(mode='json'))
            if not found: custom.append(CustomPart(id=pid,name=model,category="custom",kind="module",source_url=row.get("source","")).model_dump(mode='json'))
        except (ValueError,TypeError) as error: errors.append({"row":i,"reason":str(error)[:120]})
    return {"bom":lines,"custom_parts":custom,"errors":errors,"note":"导入报价未核对SKU与时间，保持待确认。"}


def price_leads(results: list[dict], mpn: str):
    output=[]
    identity=re.sub(r"[^a-z0-9]","",mpn.casefold())
    for hit in results:
        text=hit["title"]+" "+hit["snippet"]
        number_pattern=r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
        found=list(re.finditer(r"[¥￥]\s*"+number_pattern+"|"+number_pattern+r"\s*元",text))
        exact=bool(identity) and identity in re.sub(r"[^a-z0-9]","",text.casefold())
        if not exact: continue
        # Multiple SKU prices and similar-model tables cannot be safely assigned to the requested model.
        unique=sorted({float((m.group(1) or m.group(2)).replace(',','')) for m in found})
        link=product_link(hit["url"])
        japanese=bool(re.search(r"JPY|日元|/currency/JPY",text+' '+hit['url'],re.I))
        chinese=link['platform'] in ('淘宝','天猫','京东','立创','1688') or bool(re.search(r"人民币|CNY|RMB|\d\s*元",text,re.I))
        currency='JPY' if japanese else 'CNY' if found and chinese else 'ambiguous' if found else 'unknown'
        amount=unique[0] if len(unique)==1 and exact and currency=='CNY' and link['product_url'] else None
        title_match=identity in re.sub(r"[^a-z0-9]","",hit['title'].casefold())
        output.append({**hit,**link,"amount_cny":amount,"price_candidates_cny":unique[:10] if currency=='CNY' else [],"price_candidates_original":unique[:10],"currency":currency,"quote_type":"starting_price" if re.search(r"起价|起售|低至|元起|[¥￥]\s*\d+(?:\.\d+)?\s*起",text) else "multiple_skus_or_tiers" if len(unique)>1 else "search_snippet","status":"needs_sku_confirmation","reason":"搜索摘要只提供价格线索，需打开原页核对精确型号、裸芯片/模块/套装、数量梯度及运费。","source_url":link['product_url'] or hit["url"],"retrieved_at":datetime.now(timezone.utc).isoformat(),"model_text_matched":exact,"model_match_scope":"title_contains_target" if title_match else "target_may_be_a_component_of_this_product"})
    return sorted(output,key=lambda h:(not bool(h['product_url']),h['amount_cny'] is None))


def product_link(url: str):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    path = parsed.path.lower()
    safe_query = {k: v for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
                  if k.lower() not in ('add-to-cart', 'addtocart', 'buy_now', 'checkout', 'action')}
    clean = urlunparse(parsed._replace(query=urlencode(safe_query, doseq=True)))
    platform = next((label for domain, label in (
        ('taobao.com', '淘宝'), ('tmall.com', '天猫'), ('jd.com', '京东'),
        ('szlcsc.com', '立创'), ('1688.com', '1688'), ('digikey.com', 'DigiKey'),
        ('digikey.cn', 'DigiKey'), ('mouser.com', 'Mouser'), ('mouser.cn', 'Mouser'))
        if host == domain or host.endswith('.' + domain)), '其他来源')
    specific = (
        (platform == '淘宝' and host in ('item.taobao.com', 'h5.m.taobao.com')
         and path in ('/item.htm', '/awp/core/detail.htm') and bool(parse_qs(parsed.query).get('id')))
        or (platform == '天猫' and host == 'detail.tmall.com' and path == '/item.htm'
            and bool(parse_qs(parsed.query).get('id')))
        or (platform == '京东' and host in ('item.jd.com', 'item.m.jd.com')
            and bool(re.search(r'/(?:product/)?\d+\.html', path)))
        or (platform == '立创' and host.startswith('item.') and bool(re.search(r'/\d+\.html', path)))
        or (platform == '1688' and host == 'detail.1688.com' and bool(re.search(r'/offer/\d+', path)))
        or (platform == 'DigiKey' and '/products/detail/' in path)
        or (platform == 'Mouser' and '/productdetail/' in path)
    )
    stores = (
        ('probots.co.in', 'Probots', r'/[^/]+\.html$'),
        ('kitsguru.com', 'KitsGuru', r'/products/[^/]+'),
        ('shop.roboorion.com', 'RoboOrion', r'/products/[^/]+'),
        ('chuangzaomi.com', '创造迷', r'/product/\d+\.html'),
        ('robotshop.com', 'RobotShop', r'/products/[^/]+'),
        ('robu.in', 'Robu', r'/product/[^/]+'),
        ('robocraze.com', 'Robocraze', r'/products/[^/]+'),
        ('amazon.com', 'Amazon', r'/dp/[A-Za-z0-9]{10}'),
        ('aliexpress.com', 'AliExpress', r'/item/\d+\.html'),
        ('dfrobot.com.cn', 'DFRobot', r'/goods-\d+\.html'),
        ('dfrobot.com', 'DFRobot', r'/product-\d+\.html'),
        ('waveshare.com', 'Waveshare', r'^/[^/]+\.htm$'),
        ('pololu.com', 'Pololu', r'/product/\d+'),
        ('adafruit.com', 'Adafruit', r'/product/\d+'),
        ('keyestudio.com', 'Keyestudio', r'/products/[^/]+'),
        ('keyes-robot.com', 'Keyes', r'/pd\.jsp'),
        ('ebay.com', 'eBay', r'/itm/\d+'),
        ('newegg.com', 'Newegg', r'/p/[A-Za-z0-9-]+'),
        ('ebuy7.com', 'eBuy7', r'/[^/]+\.html$'),
        ('thinkrobotics.com', 'ThinkRobotics', r'/products/[^/]+'),
        ('theengineerstore.in', 'TheEngineerStore', r'/products/[^/]+'),
        ('item.ule.com', '邮乐', r'/mitem/item/view/\d+'),
        ('colgroad.com', 'Colgroad', r'/product/[^/]+'),
        ('taoic.com', '淘IC', r'/product/[^/]+'),
    )
    for domain, label, pattern in stores:
        if (host == domain or host.endswith('.' + domain)) and re.search(pattern, path, re.I):
            platform = label
            specific = True
            break
    specific = bool(specific and parsed.scheme in ('http', 'https') and not parsed.username and not parsed.password)
    return {'platform': platform, 'product_url': clean if specific else None,
            'link_type': 'product_detail' if specific else 'reference_source'}
