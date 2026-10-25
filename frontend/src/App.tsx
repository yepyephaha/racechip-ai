import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, Check, ChevronRight, CircleAlert, CircuitBoard, ClipboardCheck, Cpu, ExternalLink, FileSearch, FileText, FlaskConical, Info, LoaderCircle, Search, ShieldCheck, SlidersHorizontal, X } from 'lucide-react';

type Constraints = { budget_cny: number | null; max_power_w: number | null; required_interfaces: string[]; logic_voltage_v: number | null; offline_required: boolean; banned_hardware: string[];only_existing_hardware?:boolean };
type ClaimInput = {text:string;hardware_id:string;field:'io_tolerance'|'algorithm_fps'|'lifecycle'|'interface';source_url:string;sensor:string;firmware:string};
type TeamProfile = {programming:string;linux_experience:string;available_hours:number|null;existing_hardware:string[];tools:string[]};
type Signal = {direction:string;voltage_v:number|null;pin:string;level_shifter:boolean|null};
type SourceReview = {evidence_id:string;hardware_id:string;url:string;status:string;excerpt:string;locator:string;retrieved_at:string;review_method:string;hardware_reproduced:boolean};
type ClaimCheck = {claim:ClaimInput;status:string;reason:string;evidence_ids:string[];missing:string[];differing_conditions:string[]};
type VerificationAction = {title:string;steps:string[];pass_condition:string;failure_next_step:string;source_url:string;suggested_timebox_minutes:number;timebox_note:string};
type Scenario = { id: string; title: string; description: string; text: string; constraints: Constraints;claim?:ClaimInput;profile?:TeamProfile;signal_context?:Signal };
type Health = { status: string; version: string; search_mode: string; search_configured: boolean };
type Evidence = { id: string; kind: string; title: string; url: string; claim: string; field: string; accessed_at: string; status: string; excerpt: string };
type Hardware = { id: string; name: string; vendor: string; summary: string; interfaces: string[]; logic_voltage_v: number | null; power_w: number | null; price_cny: number | null; price_kind: string; capabilities: string[]; skill_level: string; docs_quality: string; evidence: unknown[]; caveats: string[] };
type CheckResult = { constraint: string; expected: unknown; actual: unknown; status: 'pass' | 'fail' | 'unknown' | 'not_requested'; reason: string };
type Recommendation = { hardware: Hardware; verdict: 'pass' | 'fail' | 'unknown'; checks: CheckResult[]; score: number; score_breakdown: { name: string; points: number; max_points: number; reason: string }[]; reasons: string[]; risks: string[]; evidence_ids: string[] };
type QueryRecord = { query: string; status: string; request_id: string | null; result_count: number; error_code?: string; [key: string]: unknown };
type Analysis = { case_id: string; created_at: string; input_text?: string; mode: string; problem: { title: string; tasks: string[]; requirements: { text: string; kind: string; source_quote: string }[]; ambiguities: string[]; parser: string }; constraints: Constraints; search: { provider: string; mode: string; status: string; queries: string[]; results: { id: string; title: string; url: string; snippet: string; kind: string; source: string; query?: string }[]; warnings: string[]; error: string | null; request_count: number; request_ids?: string[]; query_records?: QueryRecord[];new_request_count?:number;original_created_at?:string }; evidence: Evidence[]; recommendations: Recommendation[]; summary: string; warnings: string[];
claim?:ClaimInput|null;claim_checks?:ClaimCheck[];source_reviews?:SourceReview[];profile?:TeamProfile;signal_context?:Signal;playback?:boolean;
verification_actions?:VerificationAction[];suitability?:{hardware_id:string;owned:boolean;risks:string[];advantages:string[];adjustment:number;missing_inputs:string[]}[];
change_summary?:{changes:{field:string;before:unknown;after:unknown}[];reason:string;reused_evidence:boolean;new_search_requests:number};follow_up_questions?:{question:string;reason:string}[] };
const defaultProfile:TeamProfile={programming:'unknown',linux_experience:'unknown',available_hours:null,existing_hardware:[],tools:[]};
const defaultSignal:Signal={direction:'unspecified',voltage_v:null,pin:'',level_shifter:null};
const claimLabels:Record<string,string>={supported:'证据支持',contradicted:'证据冲突',conditions_differ:'条件不同',insufficient:'证据不足'};
const boardOptions=[['openmv-rt1062','OpenMV RT1062'],['openmv-h7-plus','OpenMV H7 Plus'],['maix-bit-k210','Maix Bit K210'],['esp32-s3-eye','ESP32-S3-EYE'],['raspberry-pi-5','Raspberry Pi 5']];
type Section = 'recommendations' | 'problem' | 'evidence' | 'search';
const emptyConstraints: Constraints = { budget_cny: null, max_power_w: null, required_interfaces: [], logic_voltage_v: null, offline_required: true, banned_hardware: [] };
const verdictLabel = { pass: '约束通过', unknown: '待核验', fail: '已排除', not_requested: '未要求' };
const fieldLabel: Record<string, string> = { budget: '预算', budget_cny: '预算', power: '功耗', max_power_w: '功耗', interfaces: '接口', required_interfaces: '接口', logic_voltage: '逻辑电平', logic_voltage_v: '逻辑电平', offline: '离线运行', offline_required: '离线运行', banned_hardware: '禁用硬件', banned: '禁用硬件' };
const showValue = (v: unknown): string => v === null || v === undefined ? '未知' : typeof v === 'boolean' ? (v ? '是' : '否') : Array.isArray(v) ? (v.length ? v.join('、') : '无') : typeof v === 'object' ? JSON.stringify(v) : String(v);
const safeUrl = (url: string) => /^https?:\/\//i.test(url) ? url : undefined;
const numeric = (value: string) => value.trim() === '' ? null : Number(value);
const price = (hardware: Hardware) => hardware.price_cny === null ? '价格未知' : `¥${hardware.price_cny.toLocaleString('zh-CN')} · ${hardware.price_kind === 'verified' ? '已核验报价' : '参考值，需询价'}`;
const allRisks = (item: Recommendation) => [...new Set([...item.hardware.caveats, ...item.risks])];
const visibleRisks = (item: Recommendation) => {
  const caveats = [...item.hardware.caveats].sort((a, b) => Number(/采购|电平|停产|供货|价格|供电|3\.3|5\s?V/i.test(b)) - Number(/采购|电平|停产|供货|价格|供电|3\.3|5\s?V/i.test(a)));
  return [...new Set([...caveats, ...item.risks])].slice(0, 2);
};

function download(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function report(result: Analysis) {
  const jsonBlock = (data: unknown) => `\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``;
  const parts = [
    '# 赛芯智选 RaceChip AI 选型报告',
    `案例：${result.case_id}\n生成时间：${result.created_at}\n运行模式：${result.mode === 'mock' ? 'MOCK 测试，未执行真实联网搜索' : 'LIVE 真实搜索记录'}\n历史实录：${result.playback?'是，本次打开不发起新查询':'否'}\n原始检索时间：${result.search.original_created_at||result.created_at}\n新增请求：${result.playback?0:result.search.new_request_count??result.search.request_count}\n搜索状态：${result.search.status}\n搜索错误：${result.search.error || '无'}`,
    '## 输入原文', result.input_text || '后端未提供 input_text；本导出未以当前编辑框内容替代分析时原文。',
    '## 赛题与结论', `${result.problem.title}\n\n${result.summary}`,
    '## 完整约束', jsonBlock(result.constraints),
    '## 主张核验、原文核对与队伍适配',jsonBlock({claim_checks:result.claim_checks,source_reviews:result.source_reviews,profile:result.profile,signal_context:result.signal_context,suitability:result.suitability,change_summary:result.change_summary,verification_actions:result.verification_actions,playback:result.playback||false}),
    '## 候选对比',
    result.recommendations.map(r => `### ${r.hardware.name} · ${verdictLabel[r.verdict]}\n\n排序分：${r.score}（比较指标，非成功率）\n价格：${price(r.hardware)}\n\n${r.checks.map(c => `- ${fieldLabel[c.constraint] || c.constraint}：${verdictLabel[c.status]}；要求：${showValue(c.expected)}；资料记录：${showValue(c.actual)}；${c.reason}`).join('\n')}\n\n推荐理由：${r.reasons.join('；')}\n\n完整风险：\n${allRisks(r).map(risk => `- ${risk}`).join('\n')}\n\n证据来源：\n${r.evidence_ids.map(id => { const e = result.evidence.find(entry => entry.id === id); return e ? `- ${e.title}（${id}）：${e.url}` : `- ${id}（缺少对应证据记录）`; }).join('\n')}`).join('\n\n'),
    '## 固定资料证据',
    result.evidence.map(e => `- [${e.id}] ${e.title}\n  - 来源：${e.url}\n  - 类别：${e.kind}；状态：${e.status}；字段：${e.field}\n  - 记录时间：${e.accessed_at || '未记录'}\n  - 主张：${e.claim}\n  - 摘录：${e.excerpt}`).join('\n') || '无证据记录。',
    '## 搜索运行记录',
    `提供方：${result.search.provider}\n模式：${result.search.mode}\n状态：${result.search.status}\n请求数：${result.search.request_count}\n错误：${result.search.error || '无'}\nRequestId：${result.search.request_ids?.length ? result.search.request_ids.join('、') : '未记录（不推定请求已成功）'}`,
    '### 检索式', result.search.queries.map(q => `- ${q}`).join('\n') || '无检索式。',
    '### 逐次请求记录 query_records', jsonBlock(result.search.query_records || []),
    '### 搜索返回来源',
    result.search.results.map((entry, i) => `#### ${i + 1}. ${entry.title}\n\n来源 URL：${entry.url}\n类别：${entry.kind}；来源标签：${entry.source}\n检索式：${entry.query || '未单独记录'}\n\n摘要：${entry.snippet}`).join('\n\n') || '没有搜索返回来源。',
    '## 待核验事项',
    [...new Set([...result.warnings, ...result.search.warnings, ...result.problem.ambiguities, ...(result.search.error ? [result.search.error] : [])])].map(w => `- ${w}`).join('\n') || '无新增事项。',
  ];
  return parts.join('\n\n') + '\n';
}

function Badge({ status, children }: { status: string; children?: React.ReactNode }) {
  return <span className={`badge ${status}`}>{status === 'pass' ? <Check size={12} /> : status === 'fail' ? <X size={12} /> : <span className="badge-dot" />}{children || verdictLabel[status as keyof typeof verdictLabel] || status}</span>;
}

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState('');
  const [claim,setClaim]=useState<ClaimInput|null>(null);
  const [profile,setProfile]=useState<TeamProfile>({...defaultProfile});
  const [signal,setSignal]=useState<Signal>({...defaultSignal});
  const [onlyExisting,setOnlyExisting]=useState(false);
  const [savedCases,setSavedCases]=useState<{id:string;title:string;created_at:string;query_count:number}[]>([]);
  const [problemText, setProblemText] = useState('');
  const [constraints, setConstraints] = useState<Constraints>({ ...emptyConstraints });
  const [bannedText, setBannedText] = useState('');
  const [mode, setMode] = useState<'mock' | 'live'>('mock');
  const [result, setResult] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [section, setSection] = useState<Section>('recommendations');
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const request = useRef<AbortController | null>(null);

  useEffect(() => {
    let active = true;
    Promise.allSettled([fetch('/api/health').then(r => { if (!r.ok) throw new Error('服务未就绪'); return r.json() as Promise<Health>; }), fetch('/api/scenarios').then(r => { if (!r.ok) throw new Error('示例加载失败'); return r.json() as Promise<Scenario[]>; })]).then(([h, s]) => {
      if (!active) return;
      if (h.status === 'fulfilled') {setHealth(h.value);if(h.value.search_configured)setMode('live');} else setConnectionError('暂时连接不到后端。请启动 FastAPI（默认端口 8000）后刷新。');
      if (s.status === 'fulfilled' && Array.isArray(s.value)) setScenarios(s.value);
    });
    fetch('/api/demo-cases').then(r=>r.ok?r.json():[]).then(v=>{if(active&&Array.isArray(v))setSavedCases(v);}).catch(()=>{});
    return () => { active = false; request.current?.abort(); };
  }, []);
  useEffect(() => { if (!loading) return; const timer = setInterval(() => setElapsed(v => v + 1), 1000); return () => clearInterval(timer); }, [loading]);

  function loadScenario(id: string) {
    setScenarioId(id); const scenario = scenarios.find(s => s.id === id);
    if (!scenario) return;
    setProblemText(scenario.text); setConstraints({ ...scenario.constraints }); setBannedText(scenario.constraints.banned_hardware.join('、')); setError('');
    setClaim(scenario.claim||null);setProfile(scenario.profile||{...defaultProfile});setSignal(scenario.signal_context||{...defaultSignal});setOnlyExisting(false);
  }
  function update<K extends keyof Constraints>(key: K, value: Constraints[K]) { setConstraints(current => ({ ...current, [key]: value })); }
  async function loadSaved(id:string){
    try{const response=await fetch('/api/demo-cases/'+id);if(!response.ok)throw new Error('无法载入实录');const data=await response.json() as Analysis;setResult(data);setProblemText(data.input_text||'');setConstraints(data.constraints);setProfile(data.profile||defaultProfile);setClaim(data.claim||null);setSignal(data.signal_context||defaultSignal);setBannedText(data.constraints.banned_hardware.join('、'));setOnlyExisting(!!data.constraints.only_existing_hardware);setMode('live');setSection('recommendations');setError('');setTimeout(()=>resultHeading.current?.focus(),100);}catch{setError('历史实录未能载入，请检查本机文件。');}
  }
  async function analyze(event: React.SyntheticEvent, reuse=false) {
    event.preventDefault(); if (!problemText.trim() || loading) return;
    const submittedConstraints = { ...constraints, banned_hardware: bannedText.split(/[,，、;；\n]/).map(s => s.trim()).filter(Boolean) };
    setError(''); setResult(null); setLoading(true); setElapsed(0); setSelectedEvidence(null); setSection('recommendations');
    const controller = new AbortController(); request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 150000);
    try {
      const response = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ problem_text: problemText.trim(), constraints: {...submittedConstraints,only_existing_hardware:onlyExisting}, search_mode: mode,claim,profile,signal_context:signal,previous_inputs:result?{constraints:result.constraints,profile:result.profile||defaultProfile,signal_context:result.signal_context||defaultSignal}:undefined,reuse_case_id:reuse?result?.case_id:undefined }), signal: controller.signal });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : typeof payload?.error === 'string' ? payload.error : `请求失败（HTTP ${response.status}），请检查后端日志与搜索配置。`);
      if (!payload || !Array.isArray(payload.recommendations) || !payload.problem || !payload.search) throw new Error('服务返回格式不完整，请检查后端响应。');
      setResult(payload as Analysis); setTimeout(() => resultHeading.current?.focus(), 100);
    } catch (cause) { setError(cause instanceof Error && cause.name === 'AbortError' ? '请求已取消或超过 150 秒。可以检查后端状态后重试。' : cause instanceof Error ? cause.message : '请求失败，请稍后重试。'); }
    finally { clearTimeout(timeout); request.current = null; setLoading(false); }
  }
  const recommendations = [...(result?.recommendations || [])];
  const evidence = result?.evidence.find(e => e.id === selectedEvidence);
  const warnings = [...new Set([...(result?.warnings || []), ...(result?.search.warnings || [])])];
  const liveIncomplete = result?.mode === 'live' && result.search.status !== 'ok';
  const counts = { pass: recommendations.filter(r => r.verdict === 'pass').length, unknown: recommendations.filter(r => r.verdict === 'unknown').length, fail: recommendations.filter(r => r.verdict === 'fail').length };

  return <div className="app-shell">
    <a className="skip-link" href="#workbench">跳到选型工作台</a>
    <header className="app-header">
      <a href="#workbench" className="brand" aria-label="赛芯智选首页"><span className="brand-symbol"><Cpu size={25} strokeWidth={1.6} /></span><span><strong>赛芯智选 <span>RaceChip AI</span></strong><small>电子竞赛 · 证据驱动选型</small></span></a>
      <div className="header-center"><span className="workspace-dot" />选型工作台<span className="header-separator">/</span><span>机器人视觉</span></div>
      <div className="header-status"><span className={`status-light ${health ? 'ready' : ''}`} />{health ? '本地服务已连接' : connectionError ? '服务未连接' : '正在连接服务'}<span className="version">P0 · v{health?.version || '0.1'}</span></div>
    </header>

    <main id="workbench" className="workbench">
      <aside className="input-panel">
        <div className="panel-kicker"><SlidersHorizontal size={15} />任务输入<span>01 / INPUT</span></div>
        <h1>从赛题出发。</h1><p className="intro">写下要完成的任务与限制，逐项核验硬件是否适合。</p>
        <form onSubmit={analyze}>
          <label className="field-label" htmlFor="scenario">载入演示赛题 <span>可选</span></label>
          <select id="scenario" value={scenarioId} onChange={e => loadScenario(e.target.value)}><option value="">选择一个示例，或自行输入</option>{scenarios.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
          {scenarioId && <p className="field-help">{scenarios.find(s => s.id === scenarioId)?.description}</p>}
          <label className="field-label task-label" htmlFor="problem">赛题 / 任务描述 <span>必填</span></label>
          <textarea id="problem" rows={7} required minLength={5} maxLength={12000} value={problemText} onChange={e => setProblemText(e.target.value)} placeholder="例如：为巡线机器人识别红色目标，结果通过 UART 发给主控。要求离线运行，预算 300 元以内……" />
          <div className="textarea-meta"><span>支持粘贴赛题原文</span><span>{problemText.length.toLocaleString()} / 12,000</span></div>
          <details className="investigation-input" open={!!claim}><summary>待核查说法与精确条件</summary>
            <label className="toggle-field"><input type="checkbox" checked={!!claim} onChange={e=>setClaim(e.target.checked?{text:'',hardware_id:'openmv-rt1062',field:'io_tolerance',source_url:'',sensor:'',firmware:''}:null)}/>核查一条具体说法</label>
            {claim&&<><label className="field-label">原说法<textarea rows={3} minLength={5} required value={claim.text} onChange={e=>setClaim({...claim,text:e.target.value})}/></label>
            <label className="field-label">精确型号<select value={claim.hardware_id} onChange={e=>setClaim({...claim,hardware_id:e.target.value})}>{boardOptions.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
            <label className="field-label">核查范围<select value={claim.field} onChange={e=>setClaim({...claim,field:e.target.value as ClaimInput['field']})}><option value="io_tolerance">I/O输入耐压</option><option value="algorithm_fps">算法帧率经验的适用条件</option><option value="lifecycle">生命周期与供货</option><option value="interface">接口是否有官方依据</option></select></label>
            <label className="field-label">说法原始链接<input type="url" value={claim.source_url} onChange={e=>setClaim({...claim,source_url:e.target.value})} placeholder="可留空，系统会显示证据缺口"/></label>
            <label className="field-label">传感器 / 工况<input value={claim.sensor} onChange={e=>setClaim({...claim,sensor:e.target.value})} placeholder="例如 OV5640"/></label></>}
            <label className="field-label">信号方向<select value={signal.direction} onChange={e=>setSignal({...signal,direction:e.target.value})}><option value="unspecified">尚未确认</option><option value="to_board">外部主控 → 候选板输入</option><option value="from_board">候选板输出 → 外部主控</option></select></label>
            {signal.direction!=='unspecified'&&<><label className="field-label">信号电压（V，非供电）<input type="number" min="0.1" step="0.1" value={signal.voltage_v??''} onChange={e=>setSignal({...signal,voltage_v:numeric(e.target.value)})}/></label><label className="field-label">具体数字信号引脚<input value={signal.pin} onChange={e=>setSignal({...signal,pin:e.target.value})}/></label><label className="field-label">电平转换<select value={signal.level_shifter===null?'unknown':String(signal.level_shifter)} onChange={e=>setSignal({...signal,level_shifter:e.target.value==='unknown'?null:e.target.value==='true'})}><option value="unknown">未确认</option><option value="false">没有，直接连接</option><option value="true">有转换电路（还需核对输出）</option></select></label></>}
          </details>
          <details className="investigation-input"><summary>队伍画像 · 用户自述</summary><label className="field-label">编程基础<select value={profile.programming} onChange={e=>setProfile({...profile,programming:e.target.value})}><option value="unknown">未知</option><option value="c">主要会C/C++</option><option value="python">主要会Python</option><option value="both">两者均有基础</option></select></label><label className="field-label">Linux经验<select value={profile.linux_experience} onChange={e=>setProfile({...profile,linux_experience:e.target.value})}><option value="unknown">未知</option><option value="none">没有经验</option><option value="some">有经验</option></select></label><label className="field-label">剩余可投入小时<input type="number" min="0" max="1000" value={profile.available_hours??''} onChange={e=>setProfile({...profile,available_hours:numeric(e.target.value)})}/></label>
          <fieldset className="owned-options"><legend>已有器材（持有不等于实测可用）</legend>{boardOptions.map(([id,name])=><label key={id}><input type="checkbox" checked={profile.existing_hardware.includes(id)} onChange={e=>setProfile({...profile,existing_hardware:e.target.checked?[...profile.existing_hardware,id]:profile.existing_hardware.filter(v=>v!==id)})}/>{name}</label>)}</fieldset>
          <label className="toggle-field"><input type="checkbox" checked={onlyExisting} onChange={e=>setOnlyExisting(e.target.checked)}/>只能使用现有器材（硬限制）</label>
          <label className="field-label">可用调试工具<input value={profile.tools.join('、')} onChange={e=>setProfile({...profile,tools:e.target.value.split(/[、,，]/).filter(Boolean)})} placeholder="万用表、逻辑分析仪……"/></label><p className="field-help">画像仅影响适配风险和同状态排序，不改变硬件事实。</p></details>

          <div className="section-label"><span>硬性约束</span><span className="hairline" /><ShieldCheck size={14} /></div>
          <div className="fields-grid">
            <label className="field-label" htmlFor="budget">预算上限 <div className="unit-input"><input id="budget" type="number" min="0" step="1" value={constraints.budget_cny ?? ''} onChange={e => update('budget_cny', numeric(e.target.value))} placeholder="不限" /><span>元</span></div></label>
            <label className="field-label" htmlFor="power">功耗上限 <div className="unit-input"><input id="power" type="number" min="0" step="0.1" value={constraints.max_power_w ?? ''} onChange={e => update('max_power_w', numeric(e.target.value))} placeholder="不限" /><span>W</span></div></label>
          </div>
          <fieldset className="interface-field"><legend>所需接口 <span>可多选</span></legend><div className="interface-options">{['UART', 'I2C', 'SPI', 'USB', 'CSI'].map(item => <label key={item} className={`interface-option ${constraints.required_interfaces.includes(item) ? 'checked' : ''}`}><input type="checkbox" checked={constraints.required_interfaces.includes(item)} onChange={e => update('required_interfaces', e.target.checked ? [...constraints.required_interfaces, item] : constraints.required_interfaces.filter(v => v !== item))} /><span>{item}</span></label>)}</div></fieldset>
          <div className="fields-grid lower-fields"><label className="field-label" htmlFor="voltage">主控逻辑电平<select id="voltage" value={constraints.logic_voltage_v ?? ''} onChange={e => update('logic_voltage_v', numeric(e.target.value))}><option value="">未指定</option><option value="3.3">3.3 V</option><option value="5">5 V</option><option value="1.8">1.8 V</option></select></label><label className="offline-option"><input type="checkbox" checked={constraints.offline_required} onChange={e => update('offline_required', e.target.checked)} /><span>必须离线运行<small>无需云端推理</small></span></label></div>
          <details className="advanced"><summary>禁用硬件 / 更多限制 <ChevronRight size={14} /></summary><label className="field-label" htmlFor="banned">禁止使用的型号<input id="banned" value={bannedText} onChange={e => setBannedText(e.target.value)} placeholder="用逗号分隔，例如 Raspberry Pi" /></label></details>

          <div className="section-label mode-section"><span>搜索模式</span><span className="hairline" /></div>
          <div className="mode-toggle" aria-label="搜索模式"><button type="button" className={mode === 'mock' ? 'active' : ''} aria-pressed={mode === 'mock'} onClick={() => setMode('mock')}><FlaskConical size={14} />Mock 测试</button><button type="button" className={mode === 'live' ? 'active' : ''} aria-pressed={mode === 'live'} onClick={() => setMode('live')}><Search size={14} />真实搜索</button></div>
          <p className={`mode-help ${mode === 'live' && !health?.search_configured ? 'attention' : ''}`}>{mode === 'mock' ? '使用后端测试数据，不进行联网搜索。' : health?.search_configured ? '通过后端调用搜索接口，密钥仅保存在环境变量中。' : '后端尚未报告搜索配置就绪，提交后会显示真实错误，不自动切换 Mock。'}</p>
          <button className="analyze-button" type="submit" disabled={loading || problemText.trim().length < 5}>{loading ? <><LoaderCircle size={17} className="spin" />正在核验 · {elapsed}s</> : <><FileSearch size={18} />解析赛题，开始选型<ArrowRight size={17} /></>}</button>
          {result&&<button type="button" className="recalculate-button" disabled={loading||result.input_text!==problemText||JSON.stringify(result.claim||null)!==JSON.stringify(claim)} onClick={e=>analyze(e,true)}>按已有证据重算 · 不新增搜索</button>}
          {loading && <button className="cancel-button" type="button" onClick={() => request.current?.abort()}>取消本次请求</button>}
        </form>
        <div className="input-footer"><Info size={13} /><span>缺少证据的参数保留“待核验”，不会自动视为满足。</span></div>
      </aside>

      <section className="results-panel" aria-busy={loading}>
        <div className="results-top"><div><div className="eyebrow">RACECHIP / ENGINEERING DESK</div><h2 tabIndex={-1} ref={resultHeading}>{result ? '选型核验报告' : '选型工作台'}</h2></div><div className="report-actions"><button type="button" disabled={!result || loading} onClick={() => result && download(report(result), `${result.case_id}.md`, 'text/markdown;charset=utf-8')}><ArrowDownToLine size={15} />导出报告</button><button className="icon-button" title="下载 JSON 原始结果" aria-label="下载 JSON 原始结果" type="button" disabled={!result || loading} onClick={() => result && download(JSON.stringify(result, null, 2), `${result.case_id}.json`, 'application/json')}><FileText size={16} /><span className="json-label">JSON</span></button></div></div>
        {savedCases.length>0&&<details className="saved-cases" open={!result}><summary>已完成的真实查询实录 · {savedCases.length}/3</summary><p>打开已保存记录，不发起新查询；每案保留原始时间、RequestId与来源。</p><div>{savedCases.map((item,i)=><button type="button" key={item.id} onClick={()=>loadSaved(item.id)}>实录 {String.fromCharCode(65+i)} · {new Date(item.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</button>)}</div></details>}
        <div className="workflow"><div className={result ? 'complete' : 'current'}><span>01</span><strong>解析赛题</strong><small>提取任务与边界</small></div><ChevronRight size={15} /><div className={result ? 'complete' : ''}><span>02</span><strong>核验约束</strong><small>逐项检查可行性</small></div><ChevronRight size={15} /><div className={result ? 'complete' : ''}><span>03</span><strong>追溯证据</strong><small>解释每一项推荐</small></div></div>
        {connectionError && <div className="notice error-notice" role="status"><CircleAlert size={17} /><span>{connectionError}</span></div>}
        {error && <div className="notice error-notice" role="alert"><CircleAlert size={18} /><div><strong>本次分析未完成</strong><p>{error}</p><small>没有生成替代搜索结果。修正配置或主动切换 Mock 后重试。</small></div></div>}
        {loading ? <div className="loading-state" role="status" aria-live="polite"><div className="loading-chip"><CircuitBoard size={40} /><LoaderCircle className="spin" size={21} /></div><h3>正在整理任务与证据</h3><p>{mode === 'mock' ? '后端正在运行明确标识的测试流程。' : '正在等待后端真实搜索与核验结果。'}</p><div className="loading-skeleton"><i /><i /><i /></div><small>已等待 {elapsed} 秒 · 请保留此页面</small></div> : !result ? <div className="empty-state"><div className="empty-heading"><span className="empty-icon"><CircuitBoard size={37} strokeWidth={1.4} /></span><span className="empty-id">NEW CASE / 待建立选型记录</span></div><h3>先核验能不能用，<br /><span>再解释为什么选。</span></h3><p>把赛题原文贴在左侧，补充预算、接口和供电限制。<br className="desktop-break" />系统将并列展示通过、待核验和排除项，让取舍看得见。</p><div className="sample-start"><span>从一个典型任务开始</span>{scenarios.slice(0, 3).map((s, index) => <button type="button" key={s.id} onClick={() => loadScenario(s.id)}><span className="sample-number">0{index + 1}</span><span><strong>{s.title}</strong><small>{s.description}</small></span><ArrowRight size={16} /></button>)}{!scenarios.length && <p className="no-scenarios">可直接输入自定义赛题。示例需要后端服务提供。</p>}</div><div className="evidence-principles"><div><ShieldCheck size={17} /><span>约束优先</span></div><div><ExternalLink size={16} /><span>来源可追溯</span></div><div><CircleAlert size={17} /><span>未知不猜测</span></div></div></div> : <>
          <div className={`mode-banner ${result.mode === 'mock' ? 'mock-banner' : liveIncomplete ? 'incomplete-banner' : 'live-banner'}`}>{liveIncomplete ? <CircleAlert size={18} /> : <FlaskConical size={18} />}<div><strong>{result.mode === 'mock' ? 'MOCK 测试报告' : liveIncomplete ? '实时检索未完成' : 'LIVE 真实搜索报告'}</strong><span>{result.mode === 'mock' ? '本报告使用测试检索数据；未执行真实联网搜索。' : `搜索状态：${result.search.status} · API 请求 ${result.search.request_count} 次。请结合证据状态核验结论。`}</span></div><span className="case-id">{result.case_id}</span></div>
          {result.search.error && <div className="notice error-notice report-search-error" role="alert"><CircleAlert size={18} /><div><strong>实时检索未完成</strong><p>{result.search.error}</p><small>以下固定资料不能作为本次联网核验完成的证明；未自动切换 Mock。</small></div></div>}
          {result.playback&&<div className="notice warning-notice"><Info size={18}/><span>历史真实查询实录 · {new Date(result.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}。本次打开没有发送新查询。</span></div>}
          {result.search.original_created_at&&<div className="notice warning-notice"><Info size={18}/><span>复用 {new Date(result.search.original_created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})} 的资料重算，新增搜索 {result.search.new_request_count??0} 次。原文核对时间保留。</span></div>}
          <div className="report-summary"><div><span className="eyebrow">本次任务</span><h3>{result.problem.title}</h3><p>{result.summary}</p></div><div className="verdict-counts"><div><strong>{counts.pass}</strong><span><i className="count-dot pass" />通过</span></div><div><strong>{counts.unknown}</strong><span><i className="count-dot unknown" />待核验</span></div><div><strong>{counts.fail}</strong><span><i className="count-dot fail" />排除</span></div></div></div>
          {!!result.claim_checks?.length&&<section className="claim-audit" aria-label="主张核验"><div className="content-title"><ShieldCheck size={19}/><h3>这条说法，对当前条件成立吗？</h3></div>{result.claim_checks.map((item,i)=><article key={i}><span className={'claim-status '+item.status}>{claimLabels[item.status]||item.status}</span><h4>{item.claim.text}</h4><p>{item.reason}</p>{item.differing_conditions.length>0&&<ul>{item.differing_conditions.map(v=><li key={v}>{v}</li>)}</ul>}{item.missing.length>0&&<div className="claim-missing"><strong>证据缺口</strong><ul>{item.missing.map(v=><li key={v}>{v}</li>)}</ul></div>}{item.evidence_ids.map(id=>{const original=result.source_reviews?.find(v=>v.evidence_id===id);return original?<div className="original-proof" key={id}><blockquote>{original.excerpt}</blockquote><p>{original.locator} · 原文匹配时间 {new Date(original.retrieved_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</p><SourceLink url={original.url}/><small>原文摘句匹配范围已核对；未进行硬件复现。</small></div>:null;})}</article>)}</section>}
          {!!result.follow_up_questions?.length&&<details className="followups"><summary>会影响判定的待确认问题 · {result.follow_up_questions.length}</summary>{result.follow_up_questions.map(q=><p key={q.question}><strong>{q.question}</strong><br/>{q.reason}</p>)}</details>}
          {result.change_summary&&result.change_summary.changes.length>0&&<section className="change-summary"><h3>修改后，为什么变化？</h3><p>{result.change_summary.reason}</p><ul>{result.change_summary.changes.map(v=><li key={v.field}>{({'profile.existing_hardware':'已有器材','profile.available_hours':'可投入时间','profile.programming':'编程基础','profile.linux_experience':'Linux经验','constraints.only_existing_hardware':'仅用现有器材限制'} as Record<string,string>)[v.field]||'输入条件'}：{showValue(v.before)} → {showValue(v.after)}</li>)}</ul><p>新增搜索 {result.change_summary.new_search_requests} 次；硬件事实与原文核对不会因技能变动而改变。</p></section>}
          {result.suitability&&<details className="fit-summary"><summary>队伍适配风险 · 与硬件事实分别判断</summary><p>以下按用户自述和可见产品规则计算，只影响同状态排序。</p>{result.suitability.map(item=><article key={item.hardware_id}><strong>{boardOptions.find(([id])=>id===item.hardware_id)?.[1]||item.hardware_id} · 适配调整 {item.adjustment>0?'+':''}{item.adjustment}</strong><ul>{[...item.advantages,...item.risks,...item.missing_inputs].map(v=><li key={v}>{v}</li>)}</ul></article>)}</details>}
          {!!result.verification_actions?.length&&<details className="verification-plan"><summary>下一步怎么验证 · {result.verification_actions[0].suggested_timebox_minutes}分钟建议时间预算</summary>{result.verification_actions.slice(0,result.claim?1:2).map((action,i)=><article key={i}><h4>{action.title}</h4><ol>{action.steps.map(v=><li key={v}>{v}</li>)}</ol><p><strong>通过条件：</strong>{action.pass_condition}</p><p><strong>失败后：</strong>{action.failure_next_step}</p><p>{action.timebox_note} · 尚未执行</p><SourceLink url={action.source_url}/></article>)}</details>}
          <nav className="result-tabs" aria-label="报告内容">{([{ id: 'recommendations', label: '硬件对比', count: recommendations.length }, { id: 'problem', label: '赛题解析', count: result.problem.requirements.length }, { id: 'evidence', label: '证据库', count: result.evidence.length }, { id: 'search', label: '搜索记录', count: result.search.results.length }] as { id: Section; label: string; count: number }[]).map(tab => <button type="button" key={tab.id} className={section === tab.id ? 'active' : ''} aria-pressed={section === tab.id} onClick={() => setSection(tab.id)}>{tab.label}<span>{tab.count}</span></button>)}</nav>
          {section === 'recommendations' && <div className="candidate-section"><div className="section-caption"><span>按约束状态分组，同组按解释评分排序</span><span>评分用于比较，不代表成功概率</span></div>{!recommendations.length && <div className="inline-empty">暂无候选硬件。可检查约束或检索状态后重新分析。</div>}{recommendations.map((item, index) => <article key={item.hardware.id} className={`candidate-card verdict-${item.verdict}`}><div className="candidate-top"><div className="candidate-identity"><span className="candidate-index">{String(index + 1).padStart(2, '0')}</span><div><div className="candidate-name"><h4>{item.hardware.name}</h4><Badge status={item.verdict} /></div><p>{item.hardware.vendor} <span>·</span> {item.hardware.summary}</p></div></div><div className="candidate-score"><strong>{item.score}</strong><span>排序分 · 非成功率</span></div></div><div className="hardware-specs"><span><Cpu size={13} />{item.hardware.interfaces.join(' / ') || '接口未知'}</span><span>{item.hardware.logic_voltage_v === null ? '电平待核验' : `${item.hardware.logic_voltage_v} V 逻辑电平`}</span><span>{item.hardware.power_w === null ? '功耗待核验' : `${item.hardware.power_w} W`}</span><span className="price-label">{price(item.hardware)}</span></div><div className="checks-strip" aria-label="硬性约束检查">{item.checks.filter(c => c.status !== 'not_requested').map((c, i) => <span key={`${c.constraint}-${i}`} className={`check-item ${c.status}`} title={c.reason}>{c.status === 'pass' ? <Check size={13} /> : c.status === 'fail' ? <X size={13} /> : <CircleAlert size={13} />}{fieldLabel[c.constraint] || c.constraint}<small>{c.status === 'unknown' ? '待核验' : c.status === 'fail' ? '不满足' : '满足'}</small></span>)}</div><div className="candidate-body"><div className="reason-column"><span className="small-label">推荐 / 排除理由</span><ul>{item.reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul></div><div className="risk-column"><span className="small-label">使用前优先确认</span>{visibleRisks(item).length ? <ul>{visibleRisks(item).map((risk, i) => <li key={i}>{risk}</li>)}</ul> : <p>仍需结合实物与完整赛题核验。</p>}{allRisks(item).length > 2 && <p className="more-risk-hint">另有 {allRisks(item).length - 2} 项风险，见下方全部风险。</p>}<div className="evidence-links">{item.evidence_ids.map(id => <button key={id} type="button" title={result.evidence.find(e => e.id === id)?.title || '查看相关资料'} onClick={() => { setSelectedEvidence(id); setSection('evidence'); }}><FileSearch size={12} /><span className="evidence-readable-label">{result.evidence.find(e => e.id === id)?.title || '查看相关资料'}</span><ChevronRight size={11} /></button>)}</div></div></div><details className="candidate-details"><summary>查看逐项约束、评分与全部风险 <ChevronRight size={14} /></summary><div className="table-wrap"><table><thead><tr><th>约束</th><th>要求</th><th>资料记录</th><th>结论与理由</th></tr></thead><tbody>{item.checks.map((c, i) => <tr key={i}><th>{fieldLabel[c.constraint] || c.constraint}</th><td>{showValue(c.expected)}</td><td>{showValue(c.actual)}</td><td><Badge status={c.status} /><p>{c.reason}</p></td></tr>)}</tbody></table></div><div className="score-breakdown">{item.score_breakdown.map((s, i) => <div key={i}><strong>{s.name}<span>{s.points} / {s.max_points}</span></strong><p>{s.reason}</p></div>)}</div>{allRisks(item).length > 0 && <div className="full-risk-list"><span className="small-label">全部风险与硬件备注 · {allRisks(item).length} 项</span><ul>{allRisks(item).map((risk, i) => <li key={i}>{risk}</li>)}</ul></div>}</details></article>)}</div>}
          {section === 'problem' && <div className="problem-section"><div className="content-title"><ClipboardCheck size={19} /><h3>任务拆解与原文依据</h3><span>{result.problem.parser}</span></div><details className="original-input"><summary>查看分析时的输入原文与完整约束 <ChevronRight size={14} /></summary><span className="small-label">输入原文</span><pre>{result.input_text || '后端未返回原始输入；请从导出的 JSON 核对。'}</pre><span className="small-label">完整约束</span><pre>{JSON.stringify(result.constraints, null, 2)}</pre></details><ol className="task-list">{result.problem.tasks.map((task, i) => <li key={i}><span>{String(i + 1).padStart(2, '0')}</span>{task}</li>)}</ol><div className="requirements-list">{result.problem.requirements.map((req, i) => <article key={i}><span className="small-label">{req.kind}</span><strong>{req.text}</strong><blockquote>“{req.source_quote}”</blockquote></article>)}</div>{result.problem.ambiguities.length > 0 && <div className="notice warning-notice"><CircleAlert size={18} /><div><strong>赛题仍有待确认的信息</strong><ul>{result.problem.ambiguities.map((item, i) => <li key={i}>{item}</li>)}</ul></div></div>}</div>}
          {section === 'evidence' && <div className="evidence-section"><div className="content-title"><FileSearch size={19} /><h3>逐条追溯证据</h3><span>{result.evidence.length} 条记录</span></div><p className="section-description">厂商资料用于核验参数，社区内容用于参考工程经验。测试夹具和未访问的页面不能视为本次联网核验。</p>{evidence && <article className="evidence-detail"><button type="button" className="close-detail" aria-label="关闭证据详情" onClick={() => setSelectedEvidence(null)}><X size={17} /></button><div className="eyebrow">当前证据 / {evidence.id}</div><h4>{evidence.title}</h4><p>{evidence.claim}</p><blockquote>{evidence.excerpt || '未提供可核验的摘录。'}</blockquote><dl><dt>字段</dt><dd>{evidence.field}</dd><dt>状态</dt><dd>{evidence.status}</dd><dt>记录时间</dt><dd>{evidence.accessed_at || '未记录'}</dd></dl><SourceLink url={evidence.url} /></article>}{!result.evidence.length && <div className="inline-empty">本次没有可展示的证据，所有相关参数需要进一步核验。</div>}<div className="evidence-list">{result.evidence.map(e => <article key={e.id} className={selectedEvidence === e.id ? 'selected' : ''}><div className="evidence-row-head"><span className="evidence-id">{e.id}</span><span className="source-kind">{e.kind}</span><Badge status={e.status}>{e.status}</Badge></div><button type="button" className="evidence-title" onClick={() => setSelectedEvidence(e.id)}>{e.title}<ArrowRight size={15} /></button><p>{e.claim}</p><SourceLink url={e.url} /></article>)}</div></div>}
          {section === 'search' && <div className="search-section"><div className="content-title"><Search size={19} /><h3>搜索请求与返回记录</h3><span>{result.search.provider}</span></div><div className="search-metadata"><span>模式 <strong>{result.search.mode.toUpperCase()}</strong></span><span>状态 <strong>{result.search.status}</strong></span><span>请求 <strong>{result.search.request_count} 次</strong></span></div>{result.search.error && <div className="notice error-notice"><CircleAlert size={18} /><span>{result.search.error}</span></div>}<details className="request-proof"><summary>逐次服务端凭据 · RequestId</summary>{result.search.query_records?.map((record,i)=><p key={i}><strong>查询 {i+1} · {record.status}</strong><br/>{record.query}<br/><code>{record.request_id||"没有服务端RequestId"}</code></p>)}</details><div className="query-list"><span className="small-label">检索式</span>{result.search.queries.map((query, i) => <div key={i}><Search size={13} /><code>{query}</code></div>)}</div>{!result.search.results.length && <div className="inline-empty">没有搜索结果。请结合搜索状态和错误信息判断，未生成替代内容。</div>}<div className="search-results">{result.search.results.map(item => <article key={item.id}><span className="source-kind">{item.kind} · {item.source}</span><h4>{item.title}</h4><p>{item.snippet}</p><SourceLink url={item.url} /></article>)}</div></div>}
          {warnings.length > 0 && <details className="report-warnings"><summary><CircleAlert size={15} />报告注意事项<span>{warnings.length}</span><ChevronRight size={14} /></summary><ul>{warnings.map((item, i) => <li key={i}>{item}</li>)}</ul></details>}
          <footer className="report-footer"><span>RACECHIP AI · 可追溯的工程判断</span><span>{new Date(result.created_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })} 北京时间</span></footer>
        </>}
      </section>
    </main>
  </div>;
}

function SourceLink({ url }: { url: string }) {
  const safe = safeUrl(url);
  if (!safe) return <span className="invalid-source">来源地址不可用 / 测试夹具</span>;
  let label = url; try { label = new URL(url).hostname; } catch { /* show original */ }
  return <a className="source-link" href={safe} target="_blank" rel="noopener noreferrer">{label}<ExternalLink size={12} /><span className="sr-only">，在新标签页打开来源</span></a>;
}
export default App;

