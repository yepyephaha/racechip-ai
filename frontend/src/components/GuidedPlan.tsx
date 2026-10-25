import {useEffect, useRef, useState} from 'react';
import {ArrowRight, CheckCircle2, ExternalLink, LoaderCircle, ShoppingCart} from 'lucide-react';

export type PurchaseSpec={id:string;name:string;category:string;kind:string;quantity:number;unit:string;specs:string;purpose:string;selection_reason:string;compatibility_checks:string[];search_query:string;match_terms:string[];owned:boolean;owned_quote:string;optional:boolean;package_note:string};
export type BuildPlan={title:string;summary:string;selected_route:string;selection_reason:string;options:{name:string;suitable_for:string;tradeoff:string;selected:boolean}[];purchase_items:PurchaseSpec[];coverage:{function:string;item_ids:string[];note:string}[];assembly_steps:string[];acceptance_checks:string[];unresolved:string[]};
type Product={title:string;url:string;platform:string;unit_price_cny:number|null;quote_type:string;match_status:string;missing_terms:string[];sku_verified:boolean;review_reason?:string;required_checks?:string[]};
type ChannelSearch={platform:string;status:string;result_count:number;product_count:number;error?:string|null};
type SourcedItem=PurchaseSpec&{products:Product[];references:{title:string;url:string}[];channel_searches?:ChannelSearch[];status:string;error:string|null;selection_mode?:string};
export type ProcurementJob={id:string;source_decision_id:string;conversation_id:string;sourcing_version?:number;status:string;items:SourcedItem[];completed_items:number;total_items:number;search_request_count:number;request_ids:string[];error:string|null;created_at:string;phase?:string;matching_error?:string;matching_model_calls?:{model:string;request_id:string}[];budget?:{reference_subtotal_cny:number;missing_price_items:number;note:string}};
const currentSourcingVersion=3;
type Props={plan:BuildPlan;conversationId:string;decisionId:string;ready:boolean;onApply?:(id:string)=>Promise<void>;replayJob?:ProcurementJob;replay?:boolean;managed?:boolean;managedJob?:ProcurementJob|null;autoScroll?:boolean};
const channelHref=(platform:string,query:string)=>{const q=encodeURIComponent(query);switch(platform){case'淘宝':return`https://s.taobao.com/search?q=${q}`;case'天猫':return`https://list.tmall.com/search_product.htm?q=${q}`;case'京东':return`https://search.jd.com/Search?keyword=${q}&enc=utf-8`;default:return undefined;}};
const running=(status?:string)=>status==='queued'||status==='running';

export default function GuidedPlan({plan,conversationId,decisionId,ready,onApply,replayJob,replay=false,managed=false,managedJob,autoScroll=true}:Props){
  const currentDecision=useRef(decisionId);currentDecision.current=decisionId;
  const anchor=useRef<HTMLElement>(null);
  const [job,setJob]=useState<ProcurementJob|null>(replayJob||null);
  const [error,setError]=useState('');
  const [requesting,setRequesting]=useState(false);
  const [applying,setApplying]=useState(false);
  async function start(force=false){
    setRequesting(true);setError('');
    try{
      const response=await fetch(job?.status==='interrupted'?'/api/hardware/procurement/'+job.id+'/resume':'/api/hardware/procurement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conversation_id:conversationId,decision_id:decisionId,force})});
      const data=await response.json();if(!response.ok)throw Error(data.detail||'采购检索未启动');if(currentDecision.current===decisionId)setJob(data);
    }catch(cause){setError(cause instanceof Error?cause.message:'采购检索未启动');}
    finally{setRequesting(false);}
  }
  useEffect(()=>{
    let cancelled=false;
    if(replay||managed){setJob(managed?managedJob||null:replayJob||null);return;}
    setJob(null);setError('');
    const controller=new AbortController();
    (async()=>{
      try{
        const response=await fetch('/api/hardware/procurement/latest/'+conversationId,{signal:controller.signal});
        const saved=response.ok?await response.json():null;
        if(cancelled)return;
        if(saved?.source_decision_id===decisionId&&saved.sourcing_version===currentSourcingVersion){setJob(saved);return;}
        if(ready)await start(saved?.source_decision_id===decisionId);
      }catch(cause){if(!cancelled)setError('采购状态未能恢复，可点击重新查找商品。');}
    })();
    return()=>{cancelled=true;controller.abort();};
  },[conversationId,decisionId,ready,replayJob,replay,managed,managedJob]);
  useEffect(()=>{
    if(!job||!running(job.status)||replay||managed)return;
    const controller=new AbortController();
    const timer=setInterval(async()=>{
      try{const response=await fetch('/api/hardware/procurement/'+job.id,{signal:controller.signal});if(response.ok)setJob(await response.json());}
      catch{/* A temporary network loss retains the last completed rows. */}
    },1800);
    return()=>{clearInterval(timer);controller.abort();};
  },[job?.id,job?.status,replay,managed]);
  const sourced=new Map(job?.items.map(item=>[item.id,item])||[]);
  const purchaseCount=plan.purchase_items.filter(item=>!item.owned&&!item.optional).length;
  const ownedCount=plan.purchase_items.filter(item=>item.owned).length;
  const linked=job?.items.filter(item=>!item.owned&&item.products.length>0).length||0;
  useEffect(()=>{if(ready&&autoScroll)anchor.current?.scrollIntoView({block:"start",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});},[decisionId,ready,autoScroll]);
  return <section ref={anchor} className="hw-guided-plan" aria-label="完整方案与采购清单">
    <div className="hw-plan-heading"><div><span className="hw-plan-state">{ready?'你的完整方案':'逐步形成的方案草案'}</span><h2>{plan.title}</h2><p>{plan.summary}</p></div><ShoppingCart size={24}/></div>
    <div className="hw-route-summary"><strong>{plan.selected_route}</strong><p>{plan.selection_reason}</p></div>
    {plan.options.length>0&&<details className="hw-route-options"><summary>为什么选这条路线？查看比较与取舍</summary><div>{plan.options.map(option=><article key={option.name}><h3>{option.name}{option.selected&&<span className="hw-tag pass">本次采用</span>}</h3><p>{option.suitable_for}</p><small>{option.tradeoff}</small></article>)}</div></details>}
    <div className="hw-shopping-header"><div><h3>完整采购清单</h3><p>待购{purchaseCount}项{ownedCount?` · 已有${ownedCount}项`:''} · 套装包含物与可选项单独说明</p></div>{!replay&&!managed&&<button className="hw-button" disabled={requesting||running(job?.status)} onClick={()=>start(Boolean(job))}>{requesting||running(job?.status)?<><LoaderCircle className="spin" size={15}/>元宝查找中</>:<><ShoppingCart size={15}/>{job?'重新查找商品':'用元宝补齐商品链接'}</>}</button>}</div>
    {error&&<p className="hw-model-error" role="alert">{error}</p>}
    {job&&<div className="hw-sourcing-progress" role="status"><div><strong>{running(job.status)?(job.phase==="matching_product_identities"?"正在核对商品型号与形态":`元宝逐项检索 · 已处理${job.completed_items}/${job.total_items}项`):`已处理${job.completed_items}/${job.total_items}项`}</strong><span>{linked}项有商品详情页线索 · {job.search_request_count}次元宝请求</span></div><progress value={job.completed_items} max={job.total_items}/><p>{job.status==='partial'?'部分商品未定位到详情页，已保留来源与检索词，可重新查找。':job.status==='interrupted'?'后端重启中断了检索，已取得的来源保留。':'链接只是商品页线索；价格、上架状态和精确SKU均需在商家页确认。本次没有下单或加购。'}</p>{job.error&&<p>{job.error}</p>}{job.matching_error&&<p>{job.matching_error}</p>}</div>}
    <div className="hw-shopping-grid">{plan.purchase_items.map((item,index)=>{
      const result=sourced.get(item.id);const products=result?.products||[];
      return <article className="hw-shopping-item" key={item.id}>
        <div className="hw-shopping-title"><span className="hw-shopping-number">{index+1}</span><div><small>{item.category}</small><h4>{item.name}</h4></div><strong>{item.quantity}<small>{item.unit}</small></strong></div>
        <p className="hw-shopping-specs">{item.specs}</p><p>{item.purpose}</p><p className="hw-shopping-reason">选择原因：{item.selection_reason}</p>
        {item.package_note&&<p className="hw-package-note">套装核对：{item.package_note}</p>}
        {item.owned?<div className="hw-owned"><CheckCircle2 size={15}/>你已持有，无需重复购买</div>:<>
          {item.optional&&<span className="hw-tag unknown">可选配件</span>}
          {result?.channel_searches?.length?<div className="hw-channel-results" aria-label="各购物平台检索情况">{result.channel_searches.map(channel=><span className={channel.status} key={channel.platform}><strong>{channel.platform}</strong>{channel.status==='found'?`找到${channel.product_count}个详情页`:channel.status==='error'?'检索失败':'未找到详情页'}{channel.error&&<small>{channel.error}</small>}</span>)}</div>:null}
          {products.length>0?<div className="hw-product-summary">{result?.selection_mode==='buy_together'&&<p>搜索摘要分别指向该项所需部件；购买前请先核实具体商品内容。</p>}{products.slice(0,6).map((product,i)=><div className="hw-product-summary-item" key={product.url}><span className="hw-product-summary-label">{result?.selection_mode==='buy_together'?`部件摘要 ${i+1}`:i===0?'商品搜索摘要':'其他搜索摘要'} · {product.platform}</span><small>{product.title}</small>{product.review_reason&&<small>型号与实物形态线索匹配 · 精确SKU待核对</small>}{product.match_status==='partial_text_match'&&<p>部分关键词匹配；需确认{product.missing_terms.join('、')}规格。</p>}{product.unit_price_cny!==null?<p>搜索摘要参考价 ¥{product.unit_price_cny.toFixed(2)}；SKU、套装数量与上架状态待确认。</p>:<p>搜索摘要未提供价格；请使用下方平台搜索核对当前变体、报价与库存。</p>}</div>)}</div>:<div className="hw-product-missing"><span>{running(job?.status)&&!result?'等待元宝检索':result?.status==='search_error'?'搜索未完成':job?'尚未定位到匹配的商品详情':'方案确定后自动补齐商品链接'}</span>{result?.error&&<p>{result.error}</p>}<small>检索词：{item.search_query}</small></div>}
          {result&&result.status!=='search_error'&&<nav className="hw-channel-search-links" aria-label={`${item.name}平台搜索`}>{(['淘宝','天猫','京东'] as const).map(platform=><a key={platform} href={channelHref(platform,item.search_query)} target="_blank" rel="noopener noreferrer">去{platform}搜同款<ExternalLink size={13}/></a>)}</nav>}
        </>}
        <details><summary>下单和装配前检查</summary><ul>{Array.from(new Set([...item.compatibility_checks,...products.flatMap(product=>product.required_checks||[])])).map(check=><li key={check}>{check}</li>)}</ul></details>
      </article>;
    })}</div>
    {job?.budget&&<div className="hw-purchase-budget"><strong>已取得的摘要参考价小计 ¥{job.budget.reference_subtotal_cny.toFixed(2)}</strong><span>{job.budget.missing_price_items}项缺明确价格 · 整套到手总价待确认</span><p>{job.budget.note}</p></div>}
    <div className="hw-plan-bottom"><details open><summary>整套方案的配件覆盖</summary><div className="hw-coverage">{plan.coverage.map(entry=><div key={entry.function}><CheckCircle2 size={14}/><strong>{entry.function}</strong><span>{entry.item_ids.map(id=>plan.purchase_items.find(item=>item.id===id)?.name).filter(Boolean).join(' + ')||'仍待补齐'}</span>{entry.note&&<small>{entry.note}</small>}</div>)}</div></details><details><summary>买齐后怎么装、怎样确认做成了</summary><h4>装配与联调顺序</h4><ol>{plan.assembly_steps.map(step=><li key={step}>{step}</li>)}</ol><h4>验收检查</h4><ul>{plan.acceptance_checks.map(step=><li key={step}>{step}</li>)}</ul></details>{plan.unresolved.length>0&&<details><summary>仍要核对的条件 · {plan.unresolved.length}项</summary><ul>{plan.unresolved.map(item=><li key={item}>{item}</li>)}</ul></details>}</div>
    {job&&<details className="hw-procurement-proof"><summary>元宝查询凭据 · {job.search_request_count}次真实请求</summary><p>原始记录：{new Date(job.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}（北京时间）{replay?' · 历史演示回放，本次新增请求为0':''}</p>{job.request_ids.map(id=><code key={id}>{id}</code>)}{job.matching_model_calls?.map(call=><p key={call.request_id}>商品形态核对：{call.model} · {call.request_id}</p>)}</details>}
    {!replay&&job&&onApply&&<button className="hw-primary hw-apply-plan" disabled={applying||running(job.status)} onClick={async()=>{setApplying(true);setError('');try{await onApply(job.id);}catch(cause){setError(cause instanceof Error?cause.message:'BOM合并未完成');}finally{setApplying(false);}}}>{applying?'合并中':'把完整清单加入可编辑BOM'}<ArrowRight size={16}/></button>}
  </section>;
}
