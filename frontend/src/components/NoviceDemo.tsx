import {useEffect,useRef,useState} from 'react';
import {ArrowLeft,ArrowRight,CheckCircle2,Play,RotateCcw} from 'lucide-react';
import GuidedPlan,{type BuildPlan,type ProcurementJob} from './GuidedPlan';

type Round={input:string;elapsed_seconds:number;output:{project:{conversation_id:string};assistant:{text:string;reason:string};build_plan:BuildPlan|null;decision_trace:{id:string;new_model_requests:number;new_search_requests:number}}};
type Session={notice:string;created_at:string;rounds:Round[];procurement:ProcurementJob|null};

export default function NoviceDemo({onClose}:{onClose:()=>void}){
  const [session,setSession]=useState<Session|null>(null);
  const [count,setCount]=useState(1);
  const [error,setError]=useState('');
  const log=useRef<HTMLDivElement>(null);
  useEffect(()=>{const controller=new AbortController();fetch('/api/hardware/guided-demo',{signal:controller.signal}).then(async response=>{if(!response.ok)throw Error('完整示例还在生成，请稍后再打开。');return response.json();}).then(setSession).catch(cause=>{if(!controller.signal.aborted)setError(cause.message);});return()=>controller.abort();},[]);
  useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight;},[count]);
  const round=session?.rounds[count-1];const last=Boolean(session&&count===session.rounds.length);
  return <section className="hw-novice-demo"><button className="hw-button" onClick={onClose}><ArrowLeft size={15}/>返回我的项目</button><div className="hw-page-title"><h1>一句话，走到整套采购清单</h1><p>从“我想做一个循迹小车。”开始，看看每次回答怎样改变下一问和方案。</p></div><div className="hw-demo-notice"><Play size={17}/><div><strong>模拟用户 · 真实模型与元宝记录回放</strong><p>用户回答是编排的测试输入，不是真实用户访谈。问题、方案和查询记录来自实际调用；回放新增API请求为0。</p></div></div>{error&&<p role="alert" className="hw-model-error">{error}</p>}{!session&&!error&&<p role="status">正在加载演示记录……</p>}{session&&<><div className="hw-demo-progress"><span>第{count}/{session.rounds.length}轮</span><div>{session.rounds.map((_,index)=><i className={index<count?'done':''} key={index}/>)}</div><small>记录时间：{new Date(session.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})} 北京时间</small></div><div className="hw-demo-messages hw-messages" ref={log} aria-live="polite">{session.rounds.slice(0,count).map((entry,index)=><div key={index} className={index===count-1?"hw-replay-current":undefined}><article className="user"><span>模拟用户 · 第{index+1}轮</span><p>{entry.input}</p></article><article className="assistant"><span>赛芯智选 · API上下文决策</span><p>{entry.output.assistant.text}</p><small>{entry.output.assistant.reason}</small></article></div>)}</div><div className="hw-demo-controls"><button className="hw-button" disabled={count===1} onClick={()=>setCount(count-1)}>上一轮</button><button className="hw-button" onClick={()=>setCount(1)}><RotateCcw size={14}/>从头回放</button>{!last?<button className="hw-primary" onClick={()=>setCount(count+1)}>播放下一轮回答<ArrowRight size={15}/></button>:<span><strong>已形成整套方案</strong> · 下面查看配件与商品链接</span>}</div>{last&&<div className="hw-demo-complete" role="status"><CheckCircle2 size={23}/><div><strong>从一句话，到整套配件方案。</strong><span>回放完成，继续查看选择理由、商品来源和装配检查。</span></div></div>}{last&&round?.output.build_plan&&<GuidedPlan plan={round.output.build_plan} conversationId={round.output.project.conversation_id} decisionId={round.output.decision_trace.id} ready replay replayJob={session.procurement||undefined}/>}</>}</section>;
}
