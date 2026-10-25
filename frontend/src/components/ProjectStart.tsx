import {ArrowRight, BatteryCharging, Check, CircuitBoard, Cog, Cpu, Play, Radio, Route, ScanLine, Zap} from 'lucide-react';

const starters = [
  {title:'循迹小车', description:'让小车沿着路线跑起来', prompt:'我想做一个循迹小车。', icon:Route},
  {title:'无线环境节点', description:'把温湿度数据传到 WiFi', prompt:'做一个电池供电的温湿度WiFi节点，预算300元', icon:Radio},
  {title:'稳压电源', description:'从输入、负载到供电方案', prompt:'做12V转5V的3A稳压电源', icon:Zap},
];

export function ProjectStarters({draft, onChoose}:{draft:string; onChoose:(value:string)=>void}) {
  return <div className="hw-start-options" aria-label="选择一个起步项目">
    {starters.map(({title,description,prompt,icon:Icon})=><button type="button" key={title} aria-pressed={draft===prompt} onClick={()=>onChoose(prompt)}>
      <span className="hw-start-icon"><Icon size={21} strokeWidth={1.7}/></span>
      <span><strong>{title}</strong><small>{description}</small></span>
      {draft===prompt?<Check size={18}/>:<ArrowRight size={17}/>}
    </button>)}
  </div>;
}

export function ProjectJourney({started, planned, onGuide, onDesign}:{started:boolean; planned:boolean; onGuide:()=>void; onDesign:()=>void}) {
  return <ol className="hw-journey" aria-label="从想法到工程方案">
    <li className={started?'complete':'current'}><button type="button" aria-current={!started?"step":undefined} onClick={onGuide}><span>{started?<Check size={15}/>:<MessageIcon/>}</span><strong>说出想法</strong></button></li>
    <li className={planned?'complete':started?'current':''}><button type="button" aria-current={started&&!planned?"step":undefined} onClick={onDesign}><span><CircuitBoard size={16}/></span><strong>形成方案与清单</strong></button></li>
    <li><button type="button" onClick={onDesign}><span><Check size={16}/></span><strong>核对、编辑与导出</strong></button></li>
  </ol>;
}

function MessageIcon(){return <Route size={16}/>;}

export function ExamplePreview({onPlay}:{onPlay:()=>void}) {
  return <section className="hw-example-preview" aria-label="循迹小车完整示例">
    <h2>先看看，一个想法<br/>怎样变成方案。</h2>
    <p>循迹小车 · 完整示例回放</p>
    <div className="hw-preview-diagram" role="img" aria-label="循迹小车功能示意：感知到控制再到驱动，供电支持整套系统。仅为功能示意，非接线图。">
      <svg className="hw-preview-wires" viewBox="0 0 260 150" aria-hidden="true"><path d="M65 38 H195 V112 H65 V38 M65 112 L195 38"/><path className="hw-preview-flow" d="M65 38 H195 V112 H65 V38"/></svg>
      <div><ScanLine size={23}/><span>感知</span></div><div><Cpu size={23}/><span>控制</span></div><div><BatteryCharging size={23}/><span>供电</span></div><div><Cog size={23}/><span>驱动</span></div>
    </div>
    <small className="hw-preview-caption">功能示意 · 非接线图</small>
    <button type="button" onClick={onPlay}><Play size={16} fill="currentColor"/>回放完整示例<ArrowRight size={16}/></button>
    <small>模拟用户 · 历史 API 记录 · 不发起新查询</small>
  </section>;
}
