"""Synthetic novice persona + real model decisions and Yuanbao product sourcing.

The user's answers are illustrative test inputs, never real user-research evidence.
Run explicitly: .venv/Scripts/python.exe scripts/simulate_novice.py --live
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT=Path(__file__).resolve().parents[1]


def simulated_reply(question,turn):
    if turn>=5:
        return '不用再确认小参数了，请按适合大一新生的成熟低压入门方案推荐。已确认的用途、预算和已有器材保持不变。给我整套方案和完整采购清单，技术未知项写成下单前核对事项。'
    if any(word in question for word in ('预算','花费','多少钱')):
        return '我大一，第一次做，预算200元以内，暂时什么器材都没有，电脑有USB接口。'
    if any(word in question for word in ('场景','哪里','地面','路线','室内','用途','比赛','赛道','黑线','目标','做成')):
        return '我是大一新生，想先在室内白纸上贴黑色胶带，让小车能自己沿线走一圈。是课余入门练习，不比赛，不追求高速。'
    if any(word in question for word in ('编程','基础','焊接','工具','经验')):
        return '我刚开始学C，还没有做过硬件，也没有电烙铁。希望大部分配件用插线或螺丝装好，能跟着例程学习。'
    if any(word in question for word in ('电池','供电','充电','续航')):
        return '我没有电池和充电器，演示十几分钟即可。请给我成熟的低压配套电池和匹配充电器，别让我自己组装裸电芯。'
    if any(word in question for word in ('已有','现有','器材','主控')):
        return '没有现成的板子和底盘，请一起推荐；我有电脑和普通螺丝刀，希望尽量不用焊接。'
    return '这个我还不懂，请按大一初学者、室内低速循迹、200元内、从零购买、尽量免焊接的成熟模块方案帮我选，不能确认的规格留到商品SKU核对。'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--resume',action='store_true');parser.add_argument('--refine',action='store_true');parser.add_argument('--sourcing-only',action='store_true');args=parser.parse_args()
    if not args.live:raise SystemExit('Add --live to explicitly authorize the real model/search acceptance run.')
    folder=ROOT/'artifacts/novice';folder.mkdir(parents=True,exist_ok=True)
    session={'created_at':datetime.now(timezone.utc).isoformat(),'user_input_kind':'isolated_synthetic_novice_persona',
             'notice':'用户回答是自由编排的模拟输入；问题与方案为真实TokenHub返回，商品来源为真实元宝SearchPro结果。不是用户调研结论。',
             'initial_message':'我想做一个循迹小车。','rounds':[],'procurement':None}
    save=lambda:(folder/'session.json').write_text(json.dumps(session,ensure_ascii=False,indent=2),encoding='utf-8')
    current=None;message=session['initial_message'];start_index=0
    if args.resume and (folder/'session.json').is_file():
        session=json.loads((folder/'session.json').read_text(encoding='utf-8'))
        if session['rounds']:
            current=session['rounds'][-1]['output'];start_index=len(session['rounds'])
            message=session.get('failed_input') or simulated_reply(current['assistant']['text'].split('\n')[-1],start_index)
        session.pop('error',None)
        if args.refine:
            message='上一份清单还有没替我选定的地方。请你替大一新生选定每项一种具体建议规格，不要写或、若干、待选。底盘选二驱，写清轮子直径与轴孔、电机电压；传感器选定路数和型号；电池本体、匹配充电方式、主控传感器稳定供电、开关和转接线都要列齐，不能把只有电池盒当成买了电池。没有同卖的万能配件包请拆开采购。你帮我决定，不用再追问，保留200元作为预算目标，不编价格；若实际报价不足就标待核对。'
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=320) as client:
        for index in ([] if args.sourcing_only else range(start_index,8)):
            payload={'message':message}
            if current:payload.update(project=current['project'],history=current['history'],pending_key=current['assistant']['question_key'])
            started=time.monotonic();response=client.post('/api/hardware/dialogue',json=payload)
            if response.status_code!=200:
                session['error']={'http_status':response.status_code,'detail':response.json()};session['failed_input']=message;save()
                raise SystemExit('Dialogue failed; actual response saved without a fabricated substitute.')
            current=response.json()
            session['rounds'].append({'input':message,'input_kind':'synthetic_user','output':current,'elapsed_seconds':round(time.monotonic()-started,2)})
            save()
            print(json.dumps({'round':index+1,'question':current['assistant']['text'][-500:],'ready':current['ready'],'has_build_plan':bool(current.get('build_plan')),'model_calls':current['decision_trace']['new_model_requests'],'yuanbao_calls':current['decision_trace']['new_search_requests']},ensure_ascii=False),flush=True)
            if current['ready'] and current.get('build_plan'):break
            # Only answer the current question, not keywords in its contextual preamble.
            message=simulated_reply(current['assistant']['text'].split('\n')[-1],index+1)
        else:
            if not args.sourcing_only:raise SystemExit('Model did not produce a final plan within eight turns; retained actual records.')
        if not current.get('build_plan'):raise SystemExit('No complete build plan was returned.')
        response=client.post('/api/hardware/procurement',json={'conversation_id':current['project']['conversation_id'],'decision_id':current['decision_trace']['id']})
        response.raise_for_status();job=response.json();session['procurement']=job;save()
        if job['status'] in ('interrupted','partial'):
            response=client.post('/api/hardware/procurement/'+job['id']+'/resume');response.raise_for_status();job=response.json()
        while job['status'] in ('queued','running'):
            time.sleep(2)
            try:response=client.get('/api/hardware/procurement/'+job['id'])
            except httpx.RemoteProtocolError:
                response=client.get('/api/hardware/procurement/'+job['id'])
            response.raise_for_status();job=response.json()
            if job['completed_items']!=session['procurement']['completed_items']:
                print(json.dumps({'procurement':job['completed_items'],'total':job['total_items'],'requests':job['search_request_count']},ensure_ascii=False),flush=True)
            session['procurement']=job;save()
        session['completed_at']=datetime.now(timezone.utc).isoformat()
        session.pop('failed_input',None)
        session['checks']={'real_model_decisions':all(r['output']['method']=='context_model_api' for r in session['rounds']),
                           'synthetic_user_answers_labeled':True,'purchase_item_count':len(current['build_plan']['purchase_items']),
                           'direct_product_item_count':sum(bool(item['products']) for item in job['items']),
                           'missing_product_items':job.get('missing_product_items',[]),'sku_verified':False,'hardware_tested':False}
        save();print(json.dumps(session['checks'],ensure_ascii=False),flush=True)


if __name__=='__main__':main()
