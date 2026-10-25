"""Export the actual labeled novice demo as local HTML/Markdown. Makes no API calls."""
import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'artifacts/novice'
session=json.loads((folder/'session.json').read_text(encoding='utf-8'))
plan=session['rounds'][-1]['output']['build_plan']
job=session['procurement']
escape=lambda value:html.escape(str(value))


def link(url,label):
    parsed=urlparse(url)
    if parsed.scheme not in ('http','https') or parsed.username or parsed.password:return ''
    return f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(label)} ↗</a>'


cards=[];markdown=['# '+plan['title'],'',session['notice'],'',plan['summary'],'', '## 所选路线',plan['selected_route'],plan['selection_reason'],'','## 完整采购清单','']
for index,item in enumerate(job['items'],1):
    together=item.get('selection_mode')=='buy_together'
    links=''.join('<div class="product">'+link(product['url'],f'{"一并购买" if together else "商品来源"} {position+1} · {product["platform"]}')+'<small>'+escape(product['title'])+'</small></div>' for position,product in enumerate(item['products']))
    checks=list(dict.fromkeys([*item['compatibility_checks'],*(text for product in item['products'] for text in product.get('required_checks',[]))]))
    cards.append(f'<article><div class="item-title"><span>{index}</span><h3>{escape(item["name"])}</h3><b>{item["quantity"]}<small>{escape(item["unit"])}</small></b></div><p>{escape(item["specs"])}</p><p class="muted">{escape(item["purpose"])}</p><p class="muted">选择原因：{escape(item["selection_reason"])}</p>'+('<p class="notice">以下部件需一并购买</p>' if together else '')+links+'<details><summary>下单与装配前核对</summary><ul>'+''.join('<li>'+escape(check)+'</li>' for check in checks)+'</ul></details></article>')
    markdown.extend([f'### {index}. {item["name"]} · {item["quantity"]}{item["unit"]}',item['specs'],'用途：'+item['purpose'],'选择原因：'+item['selection_reason']])
    if together:markdown.append('以下链接是不同的必需部件，需要一并购买。')
    for product in item['products']:markdown.append(f'- [{product["platform"]} · {product["title"]}](<{product["url"]}>)')
    markdown.extend(['核对：'+'；'.join(checks),''])
markdown.extend(['## 装配与联调',*['- '+step for step in plan['assembly_steps']],'','## 验收检查',*['- '+step for step in plan['acceptance_checks']],'','## 待核对条件',*['- '+step for step in plan['unresolved']],'','本页只导出已有真实记录；用户为隔离模拟输入。商品SKU、价格和硬件尚未验证。'])
(folder/'完整采购方案.md').write_text('\n'.join(markdown),encoding='utf-8')
handoff=folder/'complete-hardware-handoff.zip'
if handoff.is_file():
    with ZipFile(handoff) as archive:(folder/'shopping-list.csv').write_bytes(archive.read('shopping-list.csv'))
rounds=''.join(f'<details><summary>第{i+1}轮 · {escape(round["input"][:55])}</summary><p><b>模拟用户：</b>{escape(round["input"])}</p><p class="response"><b>实际模型回应：</b>{escape(round["output"]["assistant"]["text"])}</p></details>' for i,round in enumerate(session['rounds']))
timestamp=datetime.fromisoformat(session['created_at']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>赛芯智选 · 新生完整采购示例</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf2ee;color:#1f3028;font:15px/1.8 "Segoe UI","Microsoft YaHei",sans-serif}main{max-width:1120px;margin:24px auto;padding:32px;background:white;border:1px solid #dce4df;border-radius:12px}h1{font-size:26px;line-height:1.5}h2{font-size:21px;margin-top:32px}h3{font-size:16px;margin:0}.brand{color:#214d3b;font-weight:600}.muted,small{color:#52605a}.banner{padding:18px;background:#f5f7f5;border-radius:6px}.downloads{display:flex;gap:18px;flex-wrap:wrap;margin:22px 0}a{color:#214d3b;text-underline-offset:4px;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;align-items:start}article{padding:20px;border:1px solid #dce4df;border-radius:8px;min-width:0}.item-title{display:flex;gap:10px;align-items:start}.item-title>span{color:#52605a;font-size:13px}.item-title h3{flex:1}.item-title>b{font-size:22px;white-space:nowrap}.item-title>b>small{font-size:12px;margin-left:5px}.product{margin-top:14px}.product>a{display:block;border:1px solid #dce4df;padding:10px;border-radius:5px;text-decoration:none;font-weight:600}.product small{display:block;font-size:12px;line-height:1.8;margin:5px 0}.notice{color:#8f6418}details{border-top:1px solid #dce4df;padding:14px 0;margin-top:14px}summary{cursor:pointer;font-weight:600}.response{white-space:pre-wrap}li{margin:8px 0}code{display:inline-block;font-size:12px;color:#52605a;overflow-wrap:anywhere;margin:5px 15px 0 0}@media(max-width:760px){main{margin:0;border:0;border-radius:0;padding:24px 16px}.grid{grid-template-columns:1fr}h1{font-size:23px}a{min-height:44px}}
</style><main>'''
document+=f'<div class="brand">赛芯智选 RaceChip AI · 通用硬件工作台</div><h1>一句话开始，形成整套循迹小车采购方案</h1><div class="banner"><b>模拟用户 · 实际模型与元宝记录</b><p>{escape(session["notice"])}</p><small>示例开始时间：{timestamp} 北京时间。本页为已有记录导出，打开不发API请求。</small></div><div class="downloads"><a href="complete-hardware-handoff.zip">下载完整工程包</a><a href="shopping-list.csv">采购CSV</a><a href="完整采购方案.md">完整方案Markdown</a><a href="session.json">原始运行记录</a></div><h2>{escape(plan["title"])}</h2><p>{escape(plan["summary"])}</p><p><b>{escape(plan["selected_route"])}</b><br>{escape(plan["selection_reason"])}</p><h2>完整采购清单 · {len(job["items"])}类配件</h2><p class="muted">{sum(bool(item["products"]) for item in job["items"])}/{len(job["items"])}类已定位商品详情。具体SKU、套装数量、配套、库存与到手总价仍需打开原页核对。</p><div class="grid">'+''.join(cards)+'</div><h2>逐轮交互记录</h2>'+rounds+'<h2>装配与验收</h2><ol>'+''.join('<li>'+escape(step)+'</li>' for step in plan['assembly_steps'])+'</ol><ul>'+''.join('<li>'+escape(step)+'</li>' for step in plan['acceptance_checks'])+'</ul><h2>待核对条件</h2><ul>'+''.join('<li>'+escape(step)+'</li>' for step in plan['unresolved'])+'</ul><details><summary>已保存的元宝请求凭据</summary>'+''.join('<code>'+escape(identifier)+'</code>' for identifier in job['request_ids'])+'</details></main></html>'
(folder/'index.html').write_text(document,encoding='utf-8')
print(json.dumps({'file':'artifacts/novice/index.html','rounds':len(session['rounds']),'item_categories':len(job['items']),'linked_categories':sum(bool(item['products']) for item in job['items']),'new_api_calls':0},ensure_ascii=False))
