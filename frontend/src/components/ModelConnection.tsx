import {useState} from 'react';
import {CheckCircle2,ExternalLink,KeyRound,LoaderCircle,Settings2,X} from 'lucide-react';

export type DecisionStatus={configured:boolean;provider:string;model:string;region?:string;status:string;code?:string|null;request_id?:string|null;requires_tokenhub_key?:boolean};
type Props={status?:DecisionStatus;onChange:()=>Promise<void>;onClose:()=>void};

export default function ModelConnection({status,onChange,onClose}:Props){
  const [model,setModel]=useState(status?.model||'hy4-preview');
  const [region,setRegion]=useState(status?.region||'guangzhou');
  const [key,setKey]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [result,setResult]=useState<{status:string;message?:string;provider_message?:string;code?:string;metadata?:{request_id?:string}}|null>(null);
  async function connect(event:React.FormEvent){
    event.preventDefault();setBusy(true);setError('');setResult(null);
    try{
      const response=await fetch('/api/hardware/decision-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:key,model,region})});
      const data=await response.json();
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'配置未完成。请检查TokenHub专用Key和模型名。');
      setKey('');
      const probe=await fetch('/api/hardware/decision-probe',{method:'POST'});
      if(!probe.ok)throw new Error('模型连接验证未完成，请稍后重试。');
      const checked=await probe.json();setResult(checked);await onChange();
      if(checked.status!=='available')setError([checked.message,checked.provider_message,checked.code?`错误码：${checked.code}`:''].filter(Boolean).join(' '));
    }catch(cause){setError(cause instanceof Error?cause.message:'模型连接未完成。');}
    finally{setBusy(false);}
  }
  return <section className="hw-model-settings" aria-label="连接TokenHub决策模型"><div className="hw-model-title"><Settings2 size={18}/><div><h2>连接决策模型</h2><p>腾讯 TokenHub 负责上下文决策，元宝 SearchPro 负责搜索。</p></div><button type="button" className="hw-icon-button" aria-label="收起模型配置" onClick={onClose}><X size={18}/></button></div><div className="hw-model-layout"><div className="hw-model-guide"><ol><li>在 TokenHub 在线推理中确认模型、开通与计费条件。</li><li>在 TokenHub 的 API Key 管理中创建专用 Key。</li><li>在本机填写 Key 与模型详情页中的模型名。</li></ol><div><a href="https://console.cloud.tencent.com/tokenhub/inference" target="_blank" rel="noopener noreferrer">在线推理<ExternalLink size={13}/></a><a href="https://console.cloud.tencent.com/tokenhub/apikey" target="_blank" rel="noopener noreferrer">API Key 管理<ExternalLink size={13}/></a></div><p>旧混元已实测返回下线。AKID/SecretKey 是云标准凭据，不能直接替代 TokenHub Bearer Key。</p></div><form onSubmit={connect} autoComplete="off"><div className="hw-model-fields"><label htmlFor="model-name">模型名<span>以控制台调用示例为准</span></label><input id="model-name" value={model} onChange={e=>setModel(e.target.value)} required autoComplete="off"/><label htmlFor="model-region">服务地域</label><select id="model-region" value={region} onChange={e=>setRegion(e.target.value)}><option value="guangzhou">中国大陆 · 广州</option><option value="singapore">新加坡</option></select><label htmlFor="model-api-key">TokenHub API Key<span>{status?.configured?'留空沿用当前后端进程中的Key':'不需要填写AKID'}</span></label><div className="hw-password"><KeyRound size={15}/><input id="model-api-key" type="password" value={key} onChange={e=>setKey(e.target.value)} required={!status?.configured} placeholder={status?.configured?'已在后端配置；不回显':'粘贴TokenHub专用Key'} autoComplete="new-password" spellCheck={false}/></div></div><p className="hw-key-policy">Key 只发给本机后端，保存在进程环境中；不写入项目、浏览器存储或交付包。后端重启后需重新配置。</p><button className="hw-primary" disabled={busy||!model.trim()||(!key.trim()&&!status?.configured)}>{busy?<><LoaderCircle size={16} className="spin"/>验证连接中</>:<><CheckCircle2 size={16}/>保存并验证模型</>}</button>{error&&<div className="hw-model-error" role="alert">{error}</div>}{result?.status==='available'&&<div className="hw-model-success" role="status"><CheckCircle2 size={16}/><span>实际模型调用成功。可以返回对话继续定位需求。<small>RequestId：{result.metadata?.request_id||'供应商未返回'}</small></span></div>}</form></div></section>;
}
