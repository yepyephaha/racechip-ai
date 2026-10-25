"""Render a standalone, offline-readable index from ACTUAL saved query records."""
import html
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[1]
target = root / "artifacts" / "submission"
target.mkdir(exist_ok=True)
live_folder = root / "artifacts" / "live"
manifest = json.loads((live_folder / "manifest.json").read_text(encoding="utf-8"))
e = lambda value: html.escape(str(value))
labels = {"supported": "证据支持", "contradicted": "证据冲突", "conditions_differ": "条件不同", "insufficient": "证据不足"}
cards, lines = [], ["# 三份真实查询交付记录", "", "这些记录来自实际 SearchPro 调用；页面截图展示已保存的真实结果，不冒充再次联网。", ""]
for i, entry in enumerate(manifest["cases"]):
    name = entry["id"]
    record = json.loads((live_folder / (name + ".json")).read_text(encoding="utf-8"))
    assert record["mode"] == "live" and record["search"]["status"] == "ok"
    assert all(item["kind"] != "mock" for item in record["search"]["results"])
    letter = chr(65 + i).lower()
    check = record["claim_checks"][0]
    originals = "".join(f'<article class="source"><blockquote>{e(review["excerpt"])}</blockquote><p>{e(review["locator"])}</p><a href="{e(review["url"])}" target="_blank" rel="noopener">{e(review["url"])}</a><small>核对时间：{e(review["retrieved_at"])} · 摘句匹配，未硬件复现</small></article>' for review in record["source_reviews"] if review["status"] == "matched" and review["evidence_id"] in check["evidence_ids"])
    queries = "".join(f'<li><strong>{e(q["query"])}</strong><p>状态 {e(q["status"])} · 返回 {e(q["result_count"])} 条 · 版本 {e(q.get("version",""))}</p><code>RequestId: {e(q["request_id"])}</code></li>' for q in record["search"]["query_records"])
    links = "".join(f'<li><a href="{e(link["url"])}" target="_blank" rel="noopener">{e(link["title"])}</a></li>' for link in record["search"]["results"][:6])
    snapshot_links = f'<div class="screens"><a href="case-{letter}-claim.png"><img src="case-{letter}-claim.png" alt="案例{letter.upper()}真实结果截图"></a><a href="case-{letter}-queries.png"><img src="case-{letter}-queries.png" alt="案例{letter.upper()}查询凭据截图"></a></div>'
    cards.append(f'<section id="case-{letter}"><div class="kicker">CASE {letter.upper()} / 真实 SearchPro 记录</div><h2>{e(check["claim"]["text"])}</h2><p class="meta">执行时间 {e(record["created_at"])} · {record["search"]["request_count"]} 次请求 · {len(record["search"]["results"])} 条搜索线索</p><h3>原始问题</h3><p>{e(record["input_text"])}</p><span class="verdict {e(check["status"])}">{e(labels[check["status"]])}</span><p class="answer">{e(check["reason"])}</p><p><strong>一句话说明：</strong>{e(check["reason"])}</p>{originals}<details><summary>实际检索式、RequestId和搜索来源</summary><ol>{queries}</ol><h3>搜索线索（尚未全部核对原文）</h3><ul>{links}</ul></details><div class="actions"><a href="../live/{e(name)}.json">原始 JSON</a><a href="{e(name)}.md">完整 Markdown 报告</a></div>{snapshot_links}</section>')
    lines.extend([f'## 案例 {letter.upper()}', f'- 实际时间：{record["created_at"]}', f'- 问题：{record["input_text"]}', f'- 答案：{labels[check["status"]]}。{check["reason"]}', f'- 真实请求：{record["search"]["request_count"]}；RequestId：'+"、".join(record["search"]["request_ids"]), '- 原文来源：'+"、".join(sorted({r["url"] for r in record["source_reviews"] if r["status"] == "matched" and r["evidence_id"] in check["evidence_ids"]})), f'- 截图：case-{letter}-claim.png、case-{letter}-queries.png', f'- 原始记录：../live/{name}.json', ''])
    # Independently reproducible plain report, with all citations and actual request metadata.
    report = [f'# RaceChip AI 真实查询 {letter.upper()}', f'执行时间：{record["created_at"]}', '模式：LIVE / 元宝 SearchPro TC3；这是已保存实录，打开文件不重新搜索。',
              '## 原问题', record['input_text'], '## 原说法与结论', check['claim']['text'], labels[check['status']], check['reason'],
              '## 完整结构化结果', '```json', json.dumps(record, ensure_ascii=False, indent=2), '```']
    (target / (name + ".md")).write_text("\n\n".join(report), encoding="utf-8")
title = '赛芯智选 RaceChip AI · 三案真实查询交付'
page = '<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'
page += 'body{margin:0;background:#f4f3ec;color:#193b30;font-family:system-ui,"Microsoft YaHei",sans-serif;line-height:1.85}main{max-width:1000px;margin:auto;padding:48px 24px}header{border-bottom:2px solid #284f40;padding-bottom:28px}h1{font-size:36px;line-height:1.4}h2{font-size:25px;line-height:1.6}h3{font-size:16px;margin-top:24px}.lead{max-width:760px;color:#526055}.kicker,.meta,small{font-size:12px;color:#697268}.kicker{letter-spacing:2px}nav,.actions{display:flex;gap:18px;flex-wrap:wrap}a{color:#226647;overflow-wrap:anywhere}nav a,.actions a{padding:8px 12px;background:#e4eadf;border-radius:5px}section{margin:32px 0;background:#fffef9;padding:32px;border:1px solid #dce0d5;border-radius:8px}.answer{font-size:18px}.verdict{display:inline-block;padding:5px 12px;border-radius:4px;font-weight:700;background:#f3ead1}.contradicted{background:#f6dfd6;color:#943d28}.supported{background:#dfecdf;color:#265c36}.source{background:#f0f3e9;padding:18px;margin:20px 0;border-left:3px solid #58725b}.source blockquote{margin:0 0 10px;font-family:Georgia,serif}.source p{margin:6px 0}.source small{display:block}details{margin:20px 0;padding:16px;border:1px solid #dce0d5;border-radius:5px}summary{cursor:pointer;font-weight:600}code{font-size:12px;overflow-wrap:anywhere}.screens{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin-top:24px}.screens img{max-width:100%;max-height:700px;border:1px solid #dce0d5}footer{padding:24px 0;color:#697268;font-size:13px}@media(max-width:600px){main{padding:24px 16px}h1{font-size:27px}h2{font-size:21px}section{padding:20px}.screens{grid-template-columns:1fr}}'
page += '</style><main><header><div class="kicker">WAYTOAGI 1024 / 侦探赛道</div><h1>'+title+'</h1><p class="lead">帮助电赛新生核对硬件参数与工程经验对当前赛题是否适用。三份问题均为自拟场景，查询和原文核对实际执行于北京时间 2026-10-24。原始结果、服务端 RequestId、可点击来源和页面截图随附。</p><p><strong>实际完成：3/3 问题、9次案例查询；另有1次连通验证。重算新增请求0次。</strong></p><p>本文件是可直接打开的证据索引。完整交互应用见包内README，本机演示 <a href="http://127.0.0.1:8000/">RaceChip 工作台</a>。尚未公开部署、对外分享或正式提交。</p><nav><a href="#case-a">A · 电平冲突</a><a href="#case-b">B · 条件不同</a><a href="#case-c">C · 生命周期</a><a href="#changes">画像重算</a></nav></header>'
page += "".join(cards)
page += '<section id="changes"><div class="kicker">EXPLAINABLE RECALCULATION</div><h2>已有板卡，改变的是采购风险</h2><p>将可投入时间6小时改为12小时，并将H7 Plus加入现有器材：同状态内排序和采购风险改变，停产原文和主张状态不变。原始SearchPro资料明确复用，新增搜索请求0次。</p><a href="../live/recalculation.json">查看前后变化的真实重算 JSON</a><p><a href="condition-change.png"><img src="condition-change.png" alt="画像重算截图" style="max-width:100%;max-height:700px"></a></p></section>'
page += '<footer>资料来源只支持所述范围。搜索摘要不是已核实规格，原文摘句匹配不是硬件实验，社区经验不能保证当前帧率。价格/功耗无可靠证据时保留未知。API凭据未包含于材料。</footer></main></html>'
(target / "index.html").write_text(page, encoding="utf-8")
(target / "真实查询说明.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps({"delivery_index": str(target / "index.html"), "real_questions": manifest['successful_question_count'], "case_requests": manifest['new_request_count'], "html_bytes": len(page.encode('utf-8'))}, ensure_ascii=False))
