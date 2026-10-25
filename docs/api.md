# P0 API 与数据契约

## 当前通用工作流增量

- `POST /api/hardware/dialogue`：默认真实上下文模型。输入当前工程、消息、history；输出最多一个追问、已确认条件、模块、决策/查询凭据和可选 `build_plan`。`build_plan` 含路线取舍、完整采购规格/数量、功能覆盖、装配与验收项。不接收或生成虚构商品链接/报价。
- `GET /api/hardware/decision-status`、`POST /api/hardware/decision-config`、`POST /api/hardware/decision-probe`：分别为状态、本机模型配置与实际连通验证。配置仅更新后端进程环境。
- `POST /api/hardware/procurement`：输入 `conversation_id/decision_id`；服务端读取已保存的对应方案，返回202及任务。重复请求同一决策复用任务；明确 `force=true` 才重新检索。方案已变更返回409。任务逐项经元宝搜索，最多三项并行，每项至多三次查询。
- `GET /api/hardware/procurement/{id}`、`GET /api/hardware/procurement/latest/{conversation_id}`：恢复进度、各项商品来源、请求记录、缺口。任务状态 `queued/running/complete/partial/interrupted`；complete指已定位所需商品详情，不表示SKU、电气、机械或到手总价已核验。
- `POST /api/hardware/procurement/{id}/apply`：输入当前project，将规格和数量合并BOM；不把模型规格写入已核验facts，不替用户确认价格，同一决策重复合并不新增重复行。跨对话和旧决策拒绝套用。
- `GET /api/hardware/guided-demo`：明确标记模拟用户的历史运行；回放不重新调用模型或元宝。
- `POST /api/hardware/export`：在原有工程包上追加 `build-plan.json/md`、`procurement.json`、`shopping-list.csv`；保留历史时间与原始决策标识。

生产对话没有静默规则回退。模型结构无效或一次返回多个问题时，最多追加一次真实模型修正请求，仍失败则明确报错。`rules_demo` 只能由调用方显式指定，是离线规则示例，不能作为模型决策凭证。

## v0.2增量（以此为准）

支持两种后端鉴权：服务API KEY Bearer域名api.wsa.cloud.tencent.com，或SecretId/SecretKey的TC3域名wsa.tencentcloudapi.com；Action=SearchPro、Version=2025-05-08、不传Region。环境变量TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY，SEARCHPRO_AUTH_MODE=auto|tc3|api_key。TC3已通过实际请求验证。

AnalyzeRequest新增可选claim、profile、signal_context、previous_inputs、reuse_case_id；constraints新增only_existing_hardware。旧请求继续接受，但单数值电平不再推定完整兼容。主张限定io_tolerance/algorithm_fps/lifecycle/interface；资料未覆盖则insufficient。profile含programming、linux_experience、available_hours、existing_hardware与tools，均为用户自述。signal_context含direction、voltage_v、pin、level_shifter。

响应新增claim_checks四态、source_reviews精确原文摘句/定位/时间/SHA256、suitability、verification_actions、follow_up_questions（最多2条）、change_summary。队伍画像不改变技术事实或消除fail/unknown。验证时间仅预算。

新增GET /api/demo-cases与GET /api/demo-cases/{name}：显式读取保存的真实历史结果，playback=true，打开不发查询。GET /api/cases/{case_id}读取本进程内最多20份调查缓存。重算带reuse_case_id，要求问题/主张/模式不变，显示原始检索时间及new_request_count=0；改变任务需重新搜索，过期缓存HTTP422，不悄悄发新请求。

原文读取只允许catalog中固定URL、最多3个URL、无鉴权转发、不跟随重定向、2MB上限。有界摘句匹配才能支持相应字段；官方域名匹配本身仍仅为线索。原文匹配不等于硬件复现。

当前每次真实分析最多3个SearchPro尝试，另有有界原文核对；前端150秒取消上限。取消客户端请求不保证上游已发请求撤销。下面为旧兼容字段说明，不把其Bearer-only或90秒表述作为v0.2规范。

服务默认 `http://127.0.0.1:8000`，交互文档 `/docs`，OpenAPI `/openapi.json`。无需前端密钥。

| 方法与路径 | 返回 |
| --- | --- |
| GET /api/health | status/version/search_mode/search_configured，只披露配置布尔值 |
| GET /api/scenarios | 自编题目数组，text/constraints/expected |
| GET /api/catalog | 人工核验硬件与证据数组 |
| POST /api/analyze | 单次调查完整结果；无实时搜索权限仍返回明确 search.error |

请求示例（本身不是运行记录）：

```json
{
  "problem_text": "颜色巡线，必须UART，逻辑电平3.3V，离线运行",
  "search_mode": "mock",
  "constraints": {
    "budget_cny": null,
    "max_power_w": null,
    "required_interfaces": ["UART"],
    "logic_voltage_v": 3.3,
    "offline_required": true,
    "banned_hardware": []
  }
}
```

仅 `problem_text` 必填，5–12000有效字符。`search_mode` 只能 mock/live，默认mock。所有数值必须非负（电平必须>0），接口限定UART/I2C/SPI/USB/CSI。额外字段拒收，非法输入 HTTP422。表单留空不抹掉原文中识别到的硬限制；接口取并集、离线取或、预算/功耗取更严格上限、电平冲突标待澄清。

响应主要字段：

- `case_id / created_at / input_text / mode`：随机案例ID、北京时间、完整输入、显式运行模式。
- `problem`：紧凑title、任务标识、原句requirements、ambiguities、parser版本、unmodeled_constraints。支持color_tracking/apriltag/object_detection/line_tracking，未支持任务不给默认适用结论。
- `constraints`：原文与表单合并后的实际条件。
- `search`：provider、mode、status（mock/ok/partial/error）、queries、results、request_count、request_ids、query_records、warnings、error。request_count 是尝试HTTP次数，不能等同成功计费次数或官方额度；query_records保留每条实际发出查询、状态、RequestId和结果数量。
- `evidence`：固定资料的id/kind/title/url/claim/field/accessed_at/status/excerpt。verified表示官方原文资料已人工读到，不是硬件实测。
- `recommendations`：hardware、verdict（pass/fail/unknown）、checks、score、score_breakdown、reasons、risks、evidence_ids、live_leads。
- `summary / warnings`：条件覆盖总结和限制。

搜索状态 `error` 不代表整个HTTP请求500；UI仍展示固定库的条件评估，live覆盖条件为unknown，不能伪装为完整联网推荐。单次最多3查询，逐条执行，遇失败停止，无自动重试，不缓存。本机同一时间应只发起一项真实调查；取消浏览器请求不保证已发出的上游请求撤销。

`live_leads` 中 `official_domain_lead` 仅为检索到候选相关官方站点线索；`unverified_lead` 是其他相关线索。它们不自动变成verified规格。SearchPro `score`不进入推荐置信度。Mock结果使用example.invalid且显式kind=mock，不能作为正式来源。

官方Pages常为JSON字符串数组，adapter逐条解析；非http/https和带用户名密码链接忽略。页面摘要按文本渲染，不执行HTML。业务错误保留安全的Error.Code与RequestId，丢弃可能包含敏感内容的远端Message。HTTP429/401/503、超时、JSON异常都不回退mock。

测试使用合成板卡夹具与httpx.MockTransport；不包含真实API Key和真实SearchPro运行结果。完整固定硬件数据字段与来历见 [data-provenance.md](data-provenance.md)。
