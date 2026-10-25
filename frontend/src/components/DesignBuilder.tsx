import {useEffect,useRef,useState} from 'react';
import {ArrowRight,CheckCircle2,LoaderCircle,Search} from 'lucide-react';
import type {Project,ChatMessage,DecisionTrace} from '../HardwareWorkspace';
import GuidedPlan,{type BuildPlan,type ProcurementJob} from './GuidedPlan';
import './workflow-actions.css';

export type DesignResult={project:Project;build_plan:BuildPlan;decision_trace:DecisionTrace;history:ChatMessage[];needed_modules:string[]};
type Job={id:string;input:{project:Project;brief:string};status:string;phase:string;research?:{status:string;request_count:number;error:string|null};search_request_count:number;model_calls:{model:string;request_id:string}[];error:string|null;proposal:{message:string;assumptions:string[];next_question:{text:string;reason:string;choices:string[]}|null;links:{from_item:string;to_item:string;description:string}[]}|null;result:DesignResult|null;procurement?:ProcurementJob};
const working=(j:Job|null)=>!!j&&['queued','planning','sourcing'].includes(j.status);
const stable=(value:unknown):string=>JSON.stringify(value,(_key,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);
const read=(key:string)=>{try{return localStorage.getItem(key)||'';}catch{return '';}};
const initialBrief=(p:Project)=>!p.bom.length&&p.name!=='未命名硬件项目'?p.name:p.description;

export default function DesignBuilder({project,ready,onApply,onConfigure}:{project:Project;ready:boolean;onApply:(result:DesignResult,notice:string)=>void;onConfigure:()=>void}){
  const [brief,setBrief]=useState(()=>read('racechip-design-brief-'+project.conversation_id)||initialBrief(project));
  const [edited,setEdited]=useState(false);const [job,setJob]=useState<Job|null>(null);const [jobId,setJobId]=useState('');
  const [pollVersion,setPollVersion]=useState(0);const [submitting,setSubmitting]=useState(false);const [error,setError]=useState('');const [answer,setAnswer]=useState('');
  const [applied,setApplied]=useState('');const currentCid=useRef(project.conversation_id);const lastName=useRef(project.name);
  const [baseSnapshot,setBaseSnapshot]=useState('');
  useEffect(()=>{if(lastName.current!==project.name&&!edited&&!job)setBrief(initialBrief(project));lastName.current=project.name;},[project.name,project.description,edited,job]);
  useEffect(()=>{if(currentCid.current!==project.conversation_id)return;try{localStorage.setItem('racechip-design-brief-'+project.conversation_id,brief.replace(/AKID[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}/g,'[密钥已过滤]'));}catch{}},[brief,project.conversation_id]);
  useEffect(()=>{
    currentCid.current=project.conversation_id;setJob(null);setJobId('');setError('');setEdited(false);setApplied('');setBaseSnapshot('');
    setBrief(read('racechip-design-brief-'+project.conversation_id)||initialBrief(project));
    const controller=new AbortController();
    fetch('/api/hardware/design-runs/latest/'+project.conversation_id,{signal:controller.signal}).then(async r=>{if(r.ok){const data=await r.json();if(!controller.signal.aborted){setJob(data);setJobId(data.id);setApplied(read('racechip-design-applied-'+data.id));setBaseSnapshot(read('racechip-design-base-'+data.id));}}}).catch(()=>{});
    return()=>controller.abort();
  },[project.conversation_id]);
  useEffect(()=>{
    if(!jobId)return;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
    async function poll(){try{const response=await fetch('/api/hardware/design-runs/'+jobId,{signal:controller.signal});if(!response.ok)throw Error('方案进度暂时读取失败，可刷新后恢复。');const data=await response.json() as Job;if(controller.signal.aborted)return;setJob(data);if(working(data))timer=setTimeout(poll,1600);}catch(cause){if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'方案进度暂不可读。');}}
    poll();return()=>{controller.abort();clearTimeout(timer);};
  },[jobId,pollVersion]);
  const busy=submitting||working(job);
  const changed=!!job&&(brief.trim()!==job.input.brief||stable(project)!==(applied||baseSnapshot||stable(job.input.project)));
  const adopted=!!applied&&applied===stable(project)&&!changed;
  async function request(path:string,body:unknown){const response=await fetch('/api/hardware/design-runs'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'本次操作未完成，请检查输入与连接。');return data;}
  async function generate(event:React.FormEvent){event.preventDefault();if(busy)return;setSubmitting(true);setError('');const cid=project.conversation_id;try{const data=await request('',{project,brief:brief.trim()});if(currentCid.current!==cid)return;setJob(data);setJobId(data.id);setApplied('');const base=stable(project);setBaseSnapshot(base);try{localStorage.setItem('racechip-design-base-'+data.id,base);}catch{}setPollVersion(v=>v+1);}catch(cause){setError(cause instanceof Error?cause.message:'方案未启动。');}finally{setSubmitting(false);}}
  async function reply(text:string){setSubmitting(true);setError('');try{const data=await request('/'+job?.id+'/answer',{message:text});setJob(data);setAnswer('');setPollVersion(v=>v+1);}catch(cause){setError(cause instanceof Error?cause.message:'回答未提交。');}finally{setSubmitting(false);}}
  async function apply(){if(!job||changed)return;setSubmitting(true);setError('');try{const data=await request('/'+job.id+'/apply',project);const signature=stable(data.result.project);setApplied(signature);try{localStorage.setItem('racechip-design-applied-'+job.id,signature);}catch{}onApply(data.result,data.notice);}catch(cause){setError(cause instanceof Error?cause.message:'BOM未更新。');}finally{setSubmitting(false);}}
  return <section className="hw-design-builder" aria-label="生成或更新当前方案">
    <form className="hw-design-start" onSubmit={generate}><label htmlFor="design-goal">要做什么，或这次想怎样修改方案？</label><textarea id="design-goal" rows={3} value={brief} onChange={e=>{setBrief(e.target.value);setEdited(true);}} disabled={busy} required minLength={3} maxLength={4000} placeholder="例如：200元以内做一个室内盆栽自动浇水装置，低压供电，希望少焊接。"/><div><p>上方项目名、方向和预算是输入。点击这里后，才会检索资料、生成完整配件方案并逐件找商品。</p><button type="submit" className="hw-primary" disabled={busy||!ready||brief.trim().length<3}>{busy?<><LoaderCircle size={16} className="spin"/>正在生成与搜索</>:<><Search size={16}/>{job?'按当前修改更新方案并搜索':'生成方案并搜索配件'}</>}</button></div>{!ready&&<p className="hw-design-warning">需要连接模型和元宝搜索。<button type="button" onClick={onConfigure}>查看配置</button></p>}</form>
    {!job&&<p className="hw-design-next">生成后会出现具体模块、数量、选择理由和商品来源；采用清单后，下方BOM与系统关系图会更新。</p>}
    {error&&<p className="hw-model-error" role="alert">{error}</p>}{job?.error&&<p className="hw-model-error" role="alert">{job.error}</p>}
    {job&&<div className="hw-design-status" aria-live="polite"><strong>{job.phase}</strong><p>方案资料搜索{job.research?.request_count||0}次 · 配件搜索{job.procurement?.search_request_count||0}次{job.procurement?` · 已处理${job.procurement.completed_items}/${job.procurement.total_items}项`:''}</p><small>{working(job)?'可以切换工作区或刷新；回来后会恢复当前项目的进度。':'搜索次数为实际记录；具体SKU、报价和兼容条件仍需核对。'}</small>{changed&&<p className="hw-design-warning">当前输入或BOM已改变，这份结果对应之前的输入。请更新方案后再采用。</p>}</div>}
    {job?.research&&['partial','interrupted','error'].includes(job.status)&&!changed&&<button type="button" className="hw-button" disabled={busy} onClick={async()=>{setSubmitting(true);setError('');try{const data=await request('/'+job.id+'/resume',{});setJob(data);setPollVersion(v=>v+1);}catch(cause){setError(cause instanceof Error?cause.message:'生成任务未恢复。');}finally{setSubmitting(false);}}}>{job.procurement?'恢复未完成的配件搜索':'重试方案生成（复用已有资料）'}</button>}
    {job?.status==='needs_input'&&job.proposal?.next_question&&<section className="hw-design-question"><h3>{job.proposal.next_question.text}</h3><p>{job.proposal.next_question.reason}</p><div>{job.proposal.next_question.choices.map(c=><button type="button" className="hw-button" key={c} disabled={busy} onClick={()=>reply(c)}>{c}</button>)}</div><form onSubmit={e=>{e.preventDefault();reply(answer);}}><label htmlFor="design-answer">补充回答</label><input id="design-answer" value={answer} onChange={e=>setAnswer(e.target.value)} required maxLength={2000}/><button className="hw-primary" disabled={busy||!answer.trim()}>继续生成</button></form></section>}
    {job?.result&&<><div className="hw-design-adopt"><div><strong>{adopted?'清单已加入下方BOM':working(job)?'方案已生成，正在补齐商品来源':'方案已生成，可以采用到BOM'}</strong><p>{adopted?'可继续编辑数量、报价和连接，再核算方案。':'保留已有手工BOM与报价，新增建议规格及待核验的功能关系。'}</p></div><button type="button" className="hw-primary" onClick={apply} disabled={submitting||working(job)||changed||adopted}>{adopted?<CheckCircle2 size={16}/>:<ArrowRight size={16}/>}{adopted?'已采用':working(job)?'配件检索中':'采用清单，填入BOM'}</button>{adopted&&<button type="button" className="hw-button" onClick={()=>document.getElementById('bom-editor')?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'})}>查看BOM与连接</button>}</div>{job.proposal?.assumptions.length? <details className="hw-design-assumptions"><summary>本方案采用的建议假设 · {job.proposal.assumptions.length}项</summary><ul>{job.proposal.assumptions.map(a=><li key={a}>{a}</li>)}</ul></details>:null}<details className="hw-design-plan" open><summary>查看完整方案与商品来源</summary><GuidedPlan plan={job.result.build_plan} conversationId={job.result.project.conversation_id!} decisionId={job.result.decision_trace.id} ready managed managedJob={job.procurement} autoScroll={false}/></details></>}
  </section>;
}
