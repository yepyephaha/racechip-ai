import {useState} from 'react';
import {ArrowRight, ExternalLink, LoaderCircle, Plus, Search} from 'lucide-react';

export type DiscoveredCandidate={name:string;kind:string;category:string;source_url:string;sources:{title:string;url:string;product_url?:string|null;platform?:string}[]};
export type DiscoveryResponse={search:{status:string;mode:string;request_count:number;request_ids:string[];results:{id:string;title:string;url:string;snippet:string;product_url?:string|null;platform?:string}[];error:string|null};discovered_parts:DiscoveredCandidate[];query_variants:string[]};
const safe=(url:string)=>{try{const u=new URL(url);return /^https?:$/.test(u.protocol)&&!u.username&&!u.password?u.href:undefined;}catch{return undefined;}};

export default function DiscoveryResults({value,query,busy,error,onAdd,onQuote,onInspect,hasPart}:{value:DiscoveryResponse|null;query:string;busy:boolean;error:string;onAdd:(part:DiscoveredCandidate)=>void;onQuote:(name:string)=>void;onInspect:(name:string,url:string)=>void;hasPart:(name:string)=>boolean}){
  const [limit,setLimit]=useState(6);
  if(!value&&!busy&&!error)return <p className="hw-discovery-hint">点击搜索后，联网结果会直接显示在这里。本机未收录的型号也能查找。</p>;
  return <section className="hw-discovery-results" aria-label="当前器件的联网搜索结果" aria-live="polite">
    {busy&&<div className="hw-discovery-state" role="status"><LoaderCircle className="spin" size={17}/><div><strong>元宝正在搜索“{query}”</strong><p>正在查找型号资料与商品来源，结果会显示在搜索框下方。</p></div></div>}
    {error&&<p className="hw-model-error" role="alert">{error}</p>}
    {!busy&&value&&<><div className="hw-discovery-state"><Search size={17}/><div><strong>“{query}” · {value.search.results.length}条{value.search.mode==='live'?'联网':'模拟'}结果</strong><p>{value.search.mode==='live'?`${value.search.request_count}次真实请求`:'MOCK合成数据，未联网'} · {value.query_variants?.length>1?`也检索了分隔符写法 ${value.query_variants.slice(1).join('、')}`:'保留实际来源，可继续核对精确型号与版本'}</p></div></div>
      {value.search.error&&<p className="hw-model-error" role="alert">{value.search.error}</p>}
      {value.search.results.length===0&&<p className="hw-empty">本次没有取得可用的联网结果。可以检查型号写法，或改用功能描述；没有用本机库内容冒充搜索结果。</p>}
      {value.discovered_parts?.map(part=><article className="hw-discovered-candidate" key={part.name}><div><h3>{part.name}</h3><span>来源中有匹配文字 · 规格与形态待核验</span></div><p>{part.sources.length}份来源包含该写法，不代表独立确认或商品在售。</p><div className="hw-inline-actions"><button type="button" disabled={hasPart(part.name)} onClick={()=>onAdd(part)}><Plus size={14}/>{hasPart(part.name)?'已在BOM中':'加入BOM · 待核验'}</button><button type="button" onClick={()=>onQuote(part.name)}>查这个型号的价格<ArrowRight size={13}/></button></div></article>)}
      {value.search.results.length>0&&!value.discovered_parts?.length&&<p className="hw-discovery-hint">未自动定位到完整匹配的型号。下面是实际相关结果；可打开来源，确认后填写型号加入方案。</p>}
      <div className="hw-discovery-links">{value.search.results.slice(0,limit).map((hit,i)=><article key={hit.id+'-'+i}><a href={safe(hit.product_url||hit.url)} target="_blank" rel="noopener noreferrer">{hit.title}<ExternalLink size={14}/></a><small>{new URL(hit.url).hostname}{hit.product_url?' · 商品详情线索':' · 资料 / 网页来源'}</small><p>{hit.snippet.slice(0,220)}</p><button type="button" className="hw-button" onClick={()=>onInspect(value.discovered_parts?.[0]?.name||query,hit.product_url||hit.url)}>用这份来源录入型号</button></article>)}</div>
      {value.search.results.length>limit&&<button type="button" className="hw-button" onClick={()=>setLimit(v=>v+8)}>再显示更多来源 · 还有{value.search.results.length-limit}条</button>}
      {value.search.request_ids.length>0&&<details><summary>本次实际搜索凭据</summary>{value.search.request_ids.map(id=><code key={id}>{id}</code>)}</details>}
    </>}
  </section>;
}
