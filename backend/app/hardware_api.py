import csv
import io
import json
import re
import os
import zipfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from .hardware_models import (HardwareProject, ReviewRequest, DialogueRequest, SearchRequest, PriceRequest, DocumentInput, QuestionInput, CsvInput)
from .hardware_service import (reference_catalog, resolve_parts, review_project, dialogue, import_bom, price_leads, product_link, DOMAINS)
from .search import run_search, safe_url
from .auth import redact
from .discovery import aliases as search_aliases, candidates as discovery_candidates, normalized as normalize_part
from .decision import decide, model_call, settings as decision_settings, available_models, DecisionError

router=APIRouter(prefix="/api/hardware",tags=["通用硬件工作台"])
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/"runtime"


def store_document(name, pages, source_url=""):
    document={"id":str(uuid4()),"name":name,"pages":pages,"source_url":source_url if safe_url(source_url) else "", "imported_at":datetime.now(timezone.utc).isoformat(),"status":"user_supplied_not_independently_verified"}
    folder=RUNTIME/"documents";folder.mkdir(parents=True,exist_ok=True)
    (folder/(document["id"]+".json")).write_text(json.dumps(document,ensure_ascii=False),encoding="utf-8")
    return {k:v for k,v in document.items() if k!="pages"}|{"page_count":len(pages),"character_count":sum(len(p["text"]) for p in pages)}


@router.get("/catalog")
def get_catalog(): return {"parts":reference_catalog(),"domains":DOMAINS,"coverage":"有限的原文核验参考库，可录入任意类别的自定义器件；不宣称已覆盖全部市场型号。"}


@router.get("/examples")
def examples(): return json.loads((ROOT/"data/hardware_examples.json").read_text(encoding="utf-8"))


@router.post("/dialogue")
async def converse(request:DialogueRequest):
    if request.decision_mode=='rules_demo':
        result=dialogue(request)
        result['method']='explicit_rules_demo_not_model_decision'
        result['demo_notice']='这是明确选择的规则演示，不是上下文模型API决策。'
        return result
    try: return await decide(request)
    except DecisionError as error:
        raise HTTPException(503,{"message":error.message,"code":error.code,"request_id":error.request_id,"fallback_used":False,"provider":decision_settings()['provider']}) from None


@router.get("/decision-status")
def decision_status(): return decision_settings()


@router.get('/decision-models')
async def decision_models():return await available_models()


@router.get('/conversations/{identifier}')
def conversation_state(identifier:str):
    if not re.fullmatch(r'[a-f0-9-]{36}',identifier): raise HTTPException(404,'没有此对话')
    path=ROOT/'runtime/conversations'/(identifier+'.json')
    if not path.is_file(): raise HTTPException(404,'没有已保存的模型对话')
    return json.loads(path.read_text(encoding='utf-8'))


@router.post("/decision-probe")
async def decision_probe():
    try:
        text,meta=await model_call([{"role":"user","content":"这是接口连通测试。请仅回复OK。"}])
        return {"status":"available","response_received":bool(text),"metadata":meta}
    except DecisionError as error:
        return {"status":"unavailable","code":error.code,"message":error.message,"provider_message":error.provider_message,"request_id":error.request_id,"fallback_used":False}


@router.post("/decision-config")
async def configure_decision(request:Request):
    if request.client is None or request.client.host not in ('127.0.0.1','::1','testclient'):
        raise HTTPException(403,'模型配置只接受本机请求。')
    if not request.headers.get('content-type','').startswith('application/json'):
        raise HTTPException(415,'请使用本机配置表单。')
    origin=request.headers.get('origin')
    if origin and not re.fullmatch(r'https?://(?:127\.0\.0\.1|localhost)(?::\d+)?',origin):
        raise HTTPException(403,'模型配置只接受本机页面。')
    try:
        data=await request.json()
        key=str(data.get('api_key','')).strip() or os.environ.get('TOKENHUB_API_KEY','');model=str(data.get('model','')).strip();region=data.get('region','guangzhou')
        if not 10<=len(key)<=4096 or key.startswith('AKID'): raise ValueError('key')
        if not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}',model): raise ValueError('model')
        if region not in ('guangzhou','singapore'): raise ValueError('region')
    except Exception:
        raise HTTPException(422,'需要TokenHub专用API Key、模型名及正确地域；AKID不是TokenHub Key。输入值不会回显。') from None
    os.environ['TOKENHUB_API_KEY']=key;os.environ['TOKENHUB_MODEL']=model;os.environ['TOKENHUB_REGION']=region;os.environ['DECISION_PROVIDER']='tokenhub'
    from .decision import LAST_STATUS
    LAST_STATUS.update(status='not_tested',code=None,request_id=None)
    return {"configured":True,"provider":"tokenhub","model":model,"region":region,"storage":"backend_process_environment_only","key_returned":False}


@router.post("/review")
async def review(request:ReviewRequest):
    try: result=review_project(request.project,request.previous_project)
    except ValueError as error: raise HTTPException(422,str(error)) from None
    if request.search_mode!="off":
        parts=resolve_parts(request.project)
        names=" ".join(parts[l.part_id]["mpn"] for l in request.project.bom[:4])
        goal=request.project.description[:160]
        result["search"]=await run_search(request.search_mode,[f"{names or goal} official datasheet 接口 电源 规格",f"{names or goal} {goal[:70]} design reference application note",f"{names or goal} 工程经验 调试 问题 forum"])
    else: result["search"]={"mode":"off","status":"not_requested","request_count":0,"results":[],"queries":[],"request_ids":[],"error":None,"warnings":["本次只核算已录入资料，没有发起联网检索。"]}
    result["search_policy"]="产品联网检索统一使用元宝搜索SearchPro；搜索线索不自动改写器件规格。"
    result=json.loads(redact(json.dumps(result,ensure_ascii=False)))
    folder=RUNTIME/'reviews';folder.mkdir(parents=True,exist_ok=True)
    (folder/(result['review_id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


@router.post("/search")
async def search(request:SearchRequest):
    if re.search(r'AKID[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}',request.query):
        raise HTTPException(422,'查询中含疑似密钥，请移除后再搜索。')
    variants=search_aliases(request.query)
    result=await run_search(request.mode,[f"{request.query} {request.category} 官方 数据手册 datasheet",f"{variants[-1]} {request.category} 开发板 芯片 模块 商品 资料"])
    result["results"]=[{**hit,**product_link(hit["url"])} for hit in result["results"]]
    terms=normalize_part(request.query)
    local=[p for p in reference_catalog() if terms and terms in normalize_part(p["name"]+p["mpn"])]
    return {"search":result,"local_matches":local,"discovered_parts":discovery_candidates(request.query,result['results']) if request.mode=='live' else [],"query_variants":variants,"note":"联网结果与本机库分开展示；文字匹配不表示型号规格、形态或SKU已核实。"}


@router.post("/prices")
async def prices(request:PriceRequest):
    result=await run_search(request.mode,[f"{request.mpn} {request.item_type} 商品 价格 SKU",f"{request.mpn} {request.item_type} 报价 含税",f"{request.mpn} {request.item_type} 商品价格"],sites=["item.taobao.com","item.szlcsc.com","item.jd.com"])
    leads=price_leads(result["results"],request.mpn) if request.mode=="live" and result["status"] in ("ok","partial") else []
    return {"search":result,"price_leads":leads,"policy":"价格检索使用元宝SearchPro；商家摘要为待核对线索，需确认精确SKU、数量、裸芯片/模块/套装、税费和运费。不能把起售价当整套到手价。"}


@router.post("/compare")
def compare(payload:dict):
    try:
        project=HardwareProject(**payload.get("project",{}));parts=resolve_parts(project)
        ids=payload.get("part_ids",[])[:8]
        chosen=[parts[p] for p in ids if p in parts]
        fields=sorted({f for p in chosen for f in p.get("facts",{})})
        return {"parts":chosen,"rows":[{"field":f,"values":[p.get("facts",{}).get(f,{"value":None,"status":"unknown"}) for p in chosen],"different":len({json.dumps(p.get("facts",{}).get(f,{}).get("value"),sort_keys=True) for p in chosen})>1} for f in fields],"replacement_status":"needs_pinout_package_function_validation","note":"同类或参数相似只表示可比较；没有精确封装、引脚、功能和工况证据，不宣称Pin-to-Pin替代。"}
    except (ValueError,TypeError): raise HTTPException(422,"对比输入格式不正确") from None


@router.post("/import-bom")
def import_csv(request:CsvInput):
    try: result=import_bom(request.csv_text)
    except (ValueError,csv.Error): raise HTTPException(422,"CSV无法读取；请使用ref,mpn,quantity,unit_price_cny,source列") from None
    if not result["bom"] and not result["errors"]: raise HTTPException(422,"CSV没有有效数据行")
    return result


@router.post("/documents")
def add_document(request:DocumentInput):
    return store_document(request.name,[{"page":1,"text":request.text}],request.source_url)


@router.post("/documents/pdf")
async def add_pdf(request:Request,name:str="datasheet.pdf"):
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>10_000_000: raise HTTPException(413,"PDF最大10MB")
    if not data.startswith(b"%PDF"): raise HTTPException(422,"不是有效PDF文件")
    def extract():
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted: raise ValueError("encrypted")
        if len(reader.pages)>60: raise ValueError("too many pages")
        pages=[{"page":i+1,"text":(page.extract_text() or "")[:30000]} for i,page in enumerate(reader.pages)]
        if not any(p["text"].strip() for p in pages): raise ValueError("no text")
        return pages
    try: pages=await run_in_threadpool(extract)
    except Exception: raise HTTPException(422,"PDF无法提取文本：仅支持未加密、最多60页的文本PDF；扫描图片请提供原文摘句。") from None
    return store_document(name[:200],pages)


@router.get("/documents")
def list_documents():
    return [{"id":p.stem,"name":d["name"],"page_count":len(d["pages"]),"status":d["status"]} for p in (RUNTIME/"documents").glob("*.json") for d in [json.loads(p.read_text(encoding="utf-8"))]]


@router.post("/qa")
def qa(request:QuestionInput):
    tokens=re.findall(r"[A-Za-z0-9_.-]{2,}",request.question.lower())
    keywords={"电压":["voltage","vdd","supply","电压"],"电流":["current","电流"],"接口":["interface","i2c","spi","uart","接口"],"功耗":["power","功耗"],"温度":["temperature","温度"],"封装":["package","封装"]}
    for key,terms in keywords.items():
        if key in request.question: tokens+=terms
    chinese=re.findall(r"[\u4e00-\u9fff]{2,}",request.question)
    tokens+= [word[i:i+2] for word in chinese for i in range(len(word)-1) if word[i:i+2] not in ("多少","可以","什么","是否")]
    candidates=[]
    for doc_id in request.document_ids:
        if not re.fullmatch(r"[a-f0-9-]{36}",doc_id): continue
        path=RUNTIME/"documents"/(doc_id+".json")
        if not path.is_file(): continue
        doc=json.loads(path.read_text(encoding="utf-8"))
        for page in doc["pages"]:
            for sentence in re.split(r"[\n。;；]",page["text"]):
                if len(sentence.strip())<8: continue
                score=sum(t in sentence.lower() for t in set(tokens))
                if score: candidates.append({"score":score,"text":sentence.strip()[:700],"document":doc["name"],"page":page["page"],"source_url":doc["source_url"],"status":"user_supplied_not_independently_verified"})
    for part in reference_catalog():
        if part["id"] not in request.part_ids: continue
        for field,fact in part.get("facts",{}).items():
            text=f"{part['name']} {field}: {fact['value']} {fact['unit']}; {fact['scope']}"
            if any(t in text.lower() for t in set(tokens)):
                candidates.append({"score":2,"text":text,"document":part["name"],"page":None,"source_url":fact["source_url"],"status":fact["status"]})
    citations=sorted(candidates,key=lambda c:-c["score"])[:5]
    return {"question":request.question,"answer":"\n".join(c["text"] for c in citations) if citations else "现有资料未找到能支持该问题的片段。请补精确型号、版本或原文；不会生成无来源参数。","citations":citations,"method":"local_cited_passage_retrieval","scope":"从指定资料中检索原文片段；不是大模型推断，也未验证用户上传资料的真伪。需要全网补查请使用元宝检索。"}


@router.post("/projects")
def save_project(project:HardwareProject):
    identifier=str(uuid4());folder=RUNTIME/"projects";folder.mkdir(parents=True,exist_ok=True)
    (folder/(identifier+".json")).write_text(project.model_dump_json(indent=2),encoding="utf-8")
    return {"id":identifier,"name":project.name,"saved_at":datetime.now(timezone.utc).isoformat(),"storage":"local_server"}


@router.get("/projects")
def projects():
    return [{"id":p.stem,"name":json.loads(p.read_text(encoding="utf-8"))["name"]} for p in (RUNTIME/"projects").glob("*.json")]


@router.get("/projects/{identifier}")
def read_project(identifier:str):
    if not re.fullmatch(r"[a-f0-9-]{36}",identifier): raise HTTPException(404,"无此项目")
    path=RUNTIME/"projects"/(identifier+".json")
    if not path.is_file(): raise HTTPException(404,"无此项目")
    return json.loads(path.read_text(encoding="utf-8"))


def escaped_csv(rows):
    stream=io.StringIO();writer=csv.writer(stream)
    for row in rows:
        writer.writerow(["'"+str(x) if isinstance(x,str) and x.startswith(("=","+","-","@")) else x for x in row])
    return "\ufeff"+stream.getvalue()


@router.post("/export")
def export_project(request:ReviewRequest):
    try: result=review_project(request.project,request.previous_project)
    except ValueError as error: raise HTTPException(422,str(error)) from None
    diagram=["flowchart LR"]
    nodes={line["ref"]:f"n{i}" for i,line in enumerate(result["bom"])}
    for line in result["bom"]:
        clean_label=re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff ._-]","",line["part"]["name"])
        diagram.append(f'  {nodes[line["ref"]]}["{line["ref"]}: {clean_label}"]')
    for edge in result["architecture"]["connections"]: diagram.append(f'  {nodes[edge["from_ref"]]} -->|{edge["kind"]}| {nodes[edge["to_ref"]]}')
    bom_rows=[["ref","mpn","manufacturer","kind","quantity","unit_price_cny","quote_source","quote_kind","quote_at"]]
    for line in result["bom"]:
        bom_rows.append([line["ref"],line["part"]["mpn"],line["part"]["manufacturer"],line["part"]["kind"],line["quantity"],line["unit_price_cny"],line["quote_source"],line["quote_kind"],line["quote_at"]])
    files={"project.json":request.project.model_dump_json(indent=2),"review.json":json.dumps(result,ensure_ascii=False,indent=2),
           "bom.csv":escaped_csv(bom_rows),
           "connections.csv":escaped_csv([["from_ref","to_ref","kind","protocol","voltage_v","load_a","notes"]]+[[e.from_ref,e.to_ref,e.kind,e.protocol,e.voltage_v,e.load_a,e.notes] for e in request.project.connections]),
           "architecture.mmd":"\n".join(diagram),"handoff-netlist.json":json.dumps(result["architecture"],ensure_ascii=False,indent=2),
           "verification-plan.md":"# 验证任务（未执行）\n\n"+"\n\n".join(f"## {a['title']}\n{a['reason']}\n通过条件：{a['pass_condition']}" for a in result["verification_actions"]),
           "README.md":"# RaceChip 硬件工程交接\n\n包含BOM、连接、系统架构草案、证据与验证任务。JSON网表不是原生EDA原理图/PCB，也未完成电路/硬件测试。报价按所填信息计算，采购前核对SKU、套装和运费。"}
    files['model-status.json']=json.dumps(decision_settings(),ensure_ascii=False,indent=2)
    if request.review_id:
        path=RUNTIME/'reviews'/(request.review_id+'.json')
        if path.is_file():
            saved=json.loads(path.read_text(encoding='utf-8'))
            files['saved-search-review.json']=json.dumps({"historical_record":True,"same_project_inputs":saved.get('project')==request.project.model_dump(mode='json'),"record":saved},ensure_ascii=False,indent=2)
    if request.project.conversation_id:
        path=ROOT/'runtime/conversations'/(request.project.conversation_id+'.json')
        if path.is_file():
            saved=json.loads(path.read_text(encoding='utf-8'))
            files['saved-model-decision.json']=json.dumps({"historical_record":True,"record":saved,"note":"原始决策与查询时间保留；导出不重新调用模型或元宝。"},ensure_ascii=False,indent=2)
            if saved.get('build_plan'):
                plan=saved['build_plan']
                files['build-plan.json']=json.dumps(plan,ensure_ascii=False,indent=2)
                files['build-plan.md']='# '+plan['title']+'\n\n'+plan['summary']+'\n\n## 选择依据\n'+plan['selection_reason']+'\n\n## 组装顺序\n'+'\n'.join(f'{i+1}. {step}' for i,step in enumerate(plan['assembly_steps']))+'\n\n## 验收检查\n'+'\n'.join('- '+step for step in plan['acceptance_checks'])
            from .procurement import latest_job
            purchase=latest_job(request.project.conversation_id)
            if purchase:
                files['procurement.json']=json.dumps({'historical_record':True,'same_decision':purchase['source_decision_id']==saved.get('decision_trace',{}).get('id'),'record':purchase},ensure_ascii=False,indent=2)
                files['shopping-list.csv']=escaped_csv([['建议采购项','数量','单位','规格','已有','用途','商品来源','SKU状态']]+[[item['name'],item['quantity'],item['unit'],item['specs'],item['owned'],item['purpose'],' | '.join(p['url'] for p in item['products']),'待核对'] for item in purchase['items']])
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as bundle:
        for name,data in files.items(): bundle.writestr(name,redact(data))
    return Response(out.getvalue(),media_type="application/zip",headers={"Content-Disposition":'attachment; filename="RaceChip-hardware-handoff.zip"'})
