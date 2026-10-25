import {useEffect, useRef, useState} from 'react';
import {Bell, BellRing, Clock3, LoaderCircle, Pause, Play, Plus, RefreshCw, Trash2, TriangleAlert} from 'lucide-react';

type SourceDelta={url:string;title?:string;kind?:string;read_status?:string;published_at?:string;updated_at?:string;search_date_hint?:string};
type Event={job_id:string|null;started_at?:string;checked_at?:string;status:string;changed:boolean|null;headline?:string;summary?:string;error?:string;read_count?:number;source_count?:number;search_request_count?:number;result_fingerprint?:string;new_sources?:SourceDelta[];change_reasons?:string[];verdict_changes?:{statement?:string;verdict?:string;previous_verdict?:string}[]};
type Monitor={id:string;label:string;input:{statement:string;context:string;depth:string};interval_hours:number;enabled:boolean;status:string;next_run_at:string|null;last_run_at:string|null;last_change_at:string|null;last_error:string|null;latest_job_id:string|null;change_count:number;history:Event[]};
type Props={statement:string;context:string;depth:string;ready:boolean;searchReady:boolean;modelReady:boolean;onConfigure:()=>void;onOpenReport:(jobId:string)=>void};
const fmt=(value?:string|null)=>value?new Date(value).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):'尚未运行';
const dateLabel=(source:SourceDelta)=>{const value=source.published_at||source.updated_at||source.search_date_hint;if(!value)return '发布日期未知 · 本轮新发现';const label=source.published_at?'原文发布日期':source.updated_at?'页面更新时间':'搜索结果日期线索（未经原文确认）';const parsed=Date.parse(value);return Number.isNaN(parsed)?`${label}：${value}`:`${label}：${new Date(parsed).toLocaleDateString('zh-CN')}`;};
const verdictLabel:Record<string,string>={supported:'证据支持',contradicted:'证据反驳',conditions_differ:'需区分条件',insufficient:'证据不足'};
const safeSourceUrl=(value:string)=>{try{const url=new URL(value);return /^https?:$/.test(url.protocol)&&!url.username&&!url.password?url.href:undefined;}catch{return undefined;}};
const intervalLabel=(hours:number)=>hours<24?`每 ${hours} 小时`:hours%24===0?`每 ${hours/24} 天`:`每 ${hours} 小时`;

export default function EvidenceMonitors({statement,context,depth,ready,searchReady,modelReady,onConfigure,onOpenReport}:Props){
  const [items,setItems]=useState<Monitor[]>([]);const [interval,setInterval]=useState(24);const [busy,setBusy]=useState('');const [error,setError]=useState('');const [notice,setNotice]=useState('');const [permission,setPermission]=useState<NotificationPermission|''>('');
  const seen=useRef<Set<string>|null>(null);
  useEffect(()=>{
    if(typeof Notification!=='undefined')setPermission(Notification.permission);
    const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{
      try{
        const response=await fetch('/api/hardware/fact-check-monitors',{signal:controller.signal});if(!response.ok)throw new Error('监测列表暂时无法读取。');
        const data=await response.json() as {items:Monitor[]};if(controller.signal.aborted)return;
        const next=data.items||[];const ids=new Set(next.flatMap(item=>item.history.map(event=>event.job_id).filter((id):id is string=>!!id)));
        if(seen.current){
          for(const item of next){
            const fresh=item.history.find(event=>event.job_id&&event.changed===true&&!seen.current?.has(event.job_id));
            if(fresh){setNotice(`“${item.label}”发现新的核验变化。`);if(typeof Notification!=='undefined'&&Notification.permission==='granted')new Notification('RaceChip AI · 证据变化',{body:item.label+'：'+(fresh.headline||'核验结论或证据已变化。')});}
          }
        }
        seen.current=ids;setItems(next);setError('');
      }catch(cause){if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'监测列表暂时无法读取。');}
      if(!controller.signal.aborted)timer=setTimeout(poll,5000);
    };
    void poll();return()=>{controller.abort();clearTimeout(timer);};
  },[]);
  async function request(path:string,init?:RequestInit){
    const response=await fetch(path,init);const data=await response.json().catch(()=>null);
    if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:`操作未完成（HTTP ${response.status}）。`);
    return data;
  }
  async function create(){
    if(busy||statement.trim().length<3)return;setBusy('create');setError('');setNotice('');
    try{const item=await request('/api/hardware/fact-check-monitors',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({statement:statement.trim(),context:context.trim(),depth,interval_hours:interval})}) as Monitor;setItems(current=>[item,...current.filter(row=>row.id!==item.id)]);setNotice('已保存；首轮核查会立即开始，后续在本机服务运行时按间隔复查。');}
    catch(cause){setError(cause instanceof Error?cause.message:'无法创建持续监测。');}finally{setBusy('');}
  }
  async function update(id:string,patch:{enabled?:boolean;run?:boolean;delete?:boolean}){
    if(busy)return;setBusy(id);setError('');
    try{
      if(patch.delete){await request('/api/hardware/fact-check-monitors/'+id,{method:'DELETE'});setItems(current=>current.filter(item=>item.id!==id));setNotice('已删除这条监测。');}
      else if(patch.run){await request('/api/hardware/fact-check-monitors/'+id+'/run',{method:'POST'});setNotice('已排入立即复查。');}
      else{const item=await request('/api/hardware/fact-check-monitors/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:patch.enabled})}) as Monitor;setItems(current=>current.map(row=>row.id===id?item:row));setNotice(patch.enabled?'监测已恢复。':'监测已暂停。');}
    }catch(cause){setError(cause instanceof Error?cause.message:'操作未完成。');}finally{setBusy('');}
  }
  async function enableNotifications(){
    if(typeof Notification==='undefined'){setError('此浏览器不支持桌面通知；页面内变化提醒仍可使用。');return;}
    const result=await Notification.requestPermission();setPermission(result);setNotice(result==='granted'?'桌面变化提醒已启用。':result==='denied'?'浏览器已关闭桌面通知权限。':'桌面通知尚未授权。');
  }
  return <section className="ev-monitors" aria-labelledby="ev-monitors-title">
    <div className="ev-monitors-heading"><div><span className="ev-monitor-icon"><RefreshCw size={17}/></span><div><h2 id="ev-monitors-title">持续盯梢</h2><p>固定间隔重查同一说法；每次记录结论与来源变化。</p></div></div><button type="button" className="ev-notification-button" onClick={()=>void enableNotifications()} disabled={permission==='granted'}>{permission==='granted'?<BellRing size={15}/>:<Bell size={15}/>} {permission==='granted'?'桌面提醒已开':'启用桌面提醒'}</button></div>
    <div className="ev-monitor-create"><label htmlFor="ev-monitor-interval">复查间隔</label><select id="ev-monitor-interval" value={interval} onChange={event=>setInterval(Number(event.target.value))} disabled={busy==='create'}><option value={6}>每6小时</option><option value={24}>每天</option><option value={72}>每3天</option><option value={168}>每周</option></select><button className="hw-primary" type="button" onClick={()=>void create()} disabled={!ready||statement.trim().length<3||!!busy}><Plus size={15}/>{busy==='create'?'正在保存…':'盯梢并立即核查'}</button>{!ready&&<span className="ev-monitor-prerequisite">{!searchReady?'需要先在后端配置元宝 SearchPro 凭据。':!modelReady?'需要先配置并验证上下文模型。':''}</span>}{!modelReady&&<button className="ev-monitor-config" type="button" onClick={onConfigure}>打开模型配置</button>}</div>
    <p className="ev-monitor-local-note">任务和提醒记录保存在本机。定时核查仅在 RaceChip 后端持续运行时执行；页面关闭后，桌面提醒需浏览器保持打开。</p>
    {notice&&<p className="ev-monitor-notice" role="status" aria-live="polite">{notice}</p>}{error&&<p className="ev-monitor-error" role="alert"><TriangleAlert size={14}/>{error}</p>}
    {items.length===0?<p className="ev-monitor-empty">还没有盯梢项目。先在上方输入一句说法，选好间隔后开始。</p>:<div className="ev-monitor-list">{items.map(item=>{
      const last=item.history[item.history.length-1];
      return <article className="ev-monitor-item" key={item.id}>
        <div className="ev-monitor-main"><div><span className={'ev-monitor-state '+(item.status==='running'?'running':item.enabled?'enabled':'paused')}>{item.status==='running'?<><LoaderCircle size={12} className="ev-spin"/>首轮/本轮核查中</>:item.enabled?'盯梢中':'已暂停'}</span><span className="ev-monitor-interval"><Clock3 size={13}/>{intervalLabel(item.interval_hours)}</span></div><h3>{item.label}</h3><p>{item.input.statement}</p>{item.last_error&&<p className="ev-monitor-error"><TriangleAlert size={13}/>{item.last_error}</p>}
          {last?.changed===true&&<div className="ev-change-alert" role="status"><strong>发现证据变化</strong><span>{last.headline||'核验结果与上次不同，请展开查看。'}</span>{last.change_reasons?.length&&<small>{last.change_reasons.join(' · ')}</small>}{last.verdict_changes?.map((change,index)=><small key={`${change.statement}-${index}`}>判断变化：{change.statement} · {verdictLabel[change.previous_verdict||'']||'首次记录'} → {verdictLabel[change.verdict||'']||change.verdict}</small>)}{last.new_sources?.length&&<div className="ev-new-sources"><strong>新发现的来源</strong>{last.new_sources.slice(0,3).map(source=><span key={source.url}>{safeSourceUrl(source.url)?<a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer">{source.title||source.url}</a>:<b>{source.title||source.url}</b>}<small>{dateLabel(source)} · {source.read_status==='read'?'已读取相关原文':'仅搜索线索，尚未读取原文'}</small></span>)}{last.new_sources.length>3&&<small>另有 {last.new_sources.length-3} 条新来源</small>}</div>}</div>}
          {last?.status==='error'&&<div className="ev-monitor-result">最近一次核验未完成：{last.error||'暂无可比较的结果'}。</div>}
          {last?.status!=='error'&&last?.headline&&<div className="ev-monitor-result"><strong>{last.headline}</strong>{last.changed===false&&<span>最近一次核验未发现结论变化</span>}</div>}
          {last?.summary&&<details className="ev-monitor-summary"><summary>查看本轮核验摘要</summary><p>{last.summary}</p></details>}
          <small>上次 {fmt(item.last_run_at)} · {item.change_count} 次变化 · {item.enabled?'下次 '+fmt(item.next_run_at):'下次复查暂停'}</small>
        </div>
        <div className="ev-monitor-actions"><button type="button" className="hw-button" onClick={()=>void update(item.id,{run:true})} disabled={busy===item.id||item.status==='running'}><RefreshCw size={14}/>立即复查</button>{item.latest_job_id&&<button type="button" className="hw-button" onClick={()=>onOpenReport(item.latest_job_id!)}>查看最近核验</button>}<button type="button" className="hw-button" onClick={()=>void update(item.id,{enabled:!item.enabled})} disabled={busy===item.id||item.status==='running'}>{item.enabled?<><Pause size={14}/>暂停</>:<><Play size={14}/>恢复</>}</button><button type="button" className="ev-monitor-delete" aria-label={`删除${item.label}`} title="删除监测" onClick={()=>void update(item.id,{delete:true})} disabled={busy===item.id}><Trash2 size={15}/></button></div>
        {item.history.length>0&&<details className="ev-monitor-history"><summary>查看最近运行 · {item.history.length}</summary><ol>{[...item.history].reverse().slice(0,8).map((event,index)=><li key={event.job_id||event.started_at||index}><span>{fmt(event.checked_at||event.started_at)}</span><strong>{event.changed===true?'有变化':event.status==='running'?'正在核查':event.status==='error'?'未完成':'已核查'}</strong><small>{event.change_reasons?.join(' · ')||event.headline||event.error||`${event.read_count||0}份原文 · ${event.search_request_count||0}次搜索`}</small></li>)}</ol></details>}
      </article>;
    })}</div>}
  </section>;
}
