import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import procurement
from .hardware_models import HardwareProject

router = APIRouter(prefix='/api/hardware', tags=['完整方案与采购'])


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    conversation_id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    decision_id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    force: bool = False


class ApplyRequest(BaseModel):
    project: HardwareProject


def conversation(identifier):
    path = procurement.ROOT / 'runtime/conversations' / (identifier + '.json')
    if not path.is_file():
        raise HTTPException(404, '没有此方案对话')
    return json.loads(path.read_text(encoding='utf-8'))


@router.post('/procurement')
async def start_source(request: SourceRequest, tasks: BackgroundTasks):
    data = conversation(request.conversation_id)
    if data.get('decision_trace', {}).get('id') != request.decision_id:
        raise HTTPException(409, '需求或方案已更新，请使用最新一轮方案生成采购清单。')
    if not data.get('build_plan'):
        raise HTTPException(422, '当前还没有完整方案，请先继续需求对话。')
    job, created = procurement.create_job(data, request.force)
    if created:
        tasks.add_task(procurement.run_job, job['id'])
    return JSONResponse(job, status_code=202 if created else 200)


@router.get('/procurement/latest/{conversation_id}')
def latest_source(conversation_id: str):
    result = procurement.latest_job(conversation_id)
    if not result:
        raise HTTPException(404, '尚未生成采购清单')
    return result


@router.get('/procurement/{identifier}')
def source_status(identifier: str):
    try:
        return procurement.read_job(identifier)
    except ValueError as error:
        raise HTTPException(404, str(error)) from None


@router.post('/procurement/{identifier}/resume')
async def resume_source(identifier: str, tasks: BackgroundTasks):
    try:job=procurement.read_job(identifier)
    except ValueError as error:raise HTTPException(404,str(error)) from None
    data=conversation(job['conversation_id'])
    if data.get('decision_trace',{}).get('id')!=job['source_decision_id']:
        raise HTTPException(409,'需求已变更，请从新方案生成采购清单。')
    if identifier in procurement.ACTIVE:return job
    procurement.ACTIVE.add(identifier)
    job.update(status='queued',error=None)
    procurement.save_job(job)
    tasks.add_task(procurement.run_job,identifier)
    return JSONResponse(job,status_code=202)


@router.post('/procurement/{identifier}/apply')
def apply_source(identifier: str, request: ApplyRequest):
    try:
        job = procurement.read_job(identifier)
        latest = conversation(job['conversation_id'])
        if latest.get('decision_trace', {}).get('id') != job['source_decision_id']:
            raise HTTPException(409, '这份采购清单来自旧方案，请先按最新条件重新生成。')
        project, count = procurement.apply_to_project(job, request.project)
        return {'project': project.model_dump(mode='json'), 'added_lines': count,
                'notice': f'已将{count}项建议规格合并进BOM；精确SKU、报价与电气/机械连接仍待核验。'}
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get('/guided-demo')
def guided_demo():
    path = procurement.ROOT / 'artifacts/novice/session.json'
    if not path.is_file():
        raise HTTPException(404, '新生完整演示尚未生成')
    return json.loads(path.read_text(encoding='utf-8'))
