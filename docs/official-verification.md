# 官方规则与元宝 SearchPro 接口核验

核验日期：**2026-10-24，北京时间**。项目：赛芯智选 RaceChip AI，主投侦探赛道。本文区分“文档已核验”“实现选择”和“待实测”，文档核验不等于已成功调用搜索服务。

## 1. 官方来源与访问结果

| 编号 | 官方页面 | 本次访问 | 用途 |
| --- | --- | --- | --- |
| R1 | https://1024.waytoagi.com/ | web 成功 | 年份、赛程、主办方 |
| R2 | https://1024.waytoagi.com/rules | web 超时，Windows Invoke-WebRequest HTTP 200 | v1.0 完整规则、字段、规格、评审 |
| R3 | https://1024.waytoagi.com/tracks/detective | web 超时，Windows Invoke-WebRequest HTTP 200 | 侦探专属条件与材料 |
| A1 | https://cloud.tencent.com/document/product/1806/130615 | web 成功，Windows HTTP 200 | 服务 API KEY 认证和地址、错误 |
| A2 | https://cloud.tencent.com/document/api/1806/121811 | web 超时，Windows Invoke-WebRequest HTTP 200 | SearchPro 输入输出字段 |
| A3 | https://cloud.tencent.com/document/product/1806/121821 | web 成功 | 频率限制说明 |
| A4 | https://cloud.tencent.com/document/product/1806/130616 | web 搜索检索到官方正文 | 两种认证方式的区别 |
| A5 | https://cloud.tencent.com/document/product/1806/135870 | web 搜索检索到官方正文 | 2026-08 新字段迁移说明 |

R2、R3、A2 抓取原文分别保存在 `artifacts/official-rules.{html,txt}`、`artifacts/official-tracks-detective.{html,txt}`、`artifacts/official-searchpro.{html,txt}`，A1 存在 `artifacts/official-api-key.html`。`artifacts/official-source-index.json` 记录 URL、抓取时间、HTTP 状态和 SHA-256。这些是官方文档的本地核验快照，不是 RaceChip 的真实搜索运行记录。动态页面以后可能变化，提交前再读最新官方规则。

## 2. 影响 P0 的赛事事实

以下均为官方规则的概括，原页 R2/R3 是依据。

| 已核验要求 | 对项目的直接影响 | 来源 |
| --- | --- | --- |
| 2026-10-25 12:00 停止组队；16:00 作品提交截止；截止前允许修改重交 | 15:00 前完成首交、留出修补时间；不可把 19:02 活动结束当提交截止 | [R2](https://1024.waytoagi.com/rules) |
| 每队最多 4 人；每人最多两队、两条赛道；一件作品只投一条 | RaceChip 作品选择侦探 | [R2](https://1024.waytoagi.com/rules) |
| 侦探强调搜索为作品核心、可打开来源、查不到承认未知 | 联网证据决定“可推荐”状态；mock 仅用于测试，不能证明满足赛道条件 | [R3](https://1024.waytoagi.com/tracks/detective) |
| 侦探前三须使用元宝搜索 | 真实模式用 SearchPro，记录请求标识和来源 | [R3](https://1024.waytoagi.com/tracks/detective) |
| 可打开的作品，加三份真实提问的录屏或截图；各份含答案、简短说明、来源链接 | 见 submission-kit 三案记录模板；模拟材料不能代替这三份 | [R2](https://1024.waytoagi.com/rules)、[R3](https://1024.waytoagi.com/tracks/detective) |
| 深度调查、持续监测、截图查证为选做；做了须加对应演示 | P0 做固定三条多查询与可导出证据报告；其余列 P1，按实际完成情况申报 | [R3](https://1024.waytoagi.com/tracks/detective) |
| 每位侦探选手活动期 6000 次免费搜索；邀请码在侦探群按指引领取 | 用户本人到“我的福利”入群处理；额度生效、有效期和余量须在账户核验 | [R3](https://1024.waytoagi.com/tracks/detective) |
| 侦探前三和优秀奖要求在小红书或视频号公开分享，并附四个指定话题 | 准备文案；由用户自行发布并把链接填写到提交页 | [R3](https://1024.waytoagi.com/tracks/detective) |
| 评审权重：可用性 30%、创意 25%、场景价值 25%、展示 20% | 优先跑通三案与三分钟展示，再扩展 P1 | [R2](https://1024.waytoagi.com/rules) |
| 原创，保证第三方资源使用权限；不要求开源；参评作品公开 | 提交工具披露和来源；体验账号只供评委，密钥不进入材料 | [R2](https://1024.waytoagi.com/rules) |

四个分享话题：`#元宝搜索 #WaytoAGI #AI切磋大会 #1024超能Coding周末`。[官方来源](https://1024.waytoagi.com/tracks/detective)

## 3. P0 采用的 SearchPro HTTP 契约

采用**服务 API KEY**，不采用腾讯云 SecretId/SecretKey 签名流程。[A1](https://cloud.tencent.com/document/product/1806/130615)

```http
POST https://api.wsa.cloud.tencent.com/SearchPro
Authorization: Bearer <仅由后端环境变量读取>
Content-Type: application/json; charset=UTF-8

{"Query":"OpenMV Cam H7 Plus 官方 RAM UART 摄像头"}
```

环境变量沿用官方示例：`TENCENTCLOUD_WSA_APIKEY`。只在后端读取；前端不使用 `VITE_` 密钥；日志、报告、截图和异常均不得输出请求头。上面的 body 是请求格式示例，未声称已发出实际搜索。[A1](https://cloud.tencent.com/document/product/1806/130615)

标准云 API 域名 `wsa.tencentcloudapi.com` 使用另一套签名、公参（Action=SearchPro、Version=2025-05-08）。不要将其与上述 Bearer 地址混用。[A2](https://cloud.tencent.com/document/api/1806/121811)、[A4](https://cloud.tencent.com/document/product/1806/130616)

### 3.1 输入参数

依据 [SearchPro 官方 REST 文档](https://cloud.tencent.com/document/api/1806/121811)：

| 参数 | 类型与取值 | P0 使用策略 |
| --- | --- | --- |
| Query | 必填 string，检索语句 | 由赛题、候选型号、待核验属性生成独立查询 |
| Site | 可选 string，单域包含；`exclude:a.com\|b.com` 排除，最多五域 | 官方参数检索与社区检索分开；仍须验证返回 URL 主机名 |
| Mode | 可选 integer：0/1/2，自然/垂直/混合；极速版不支持 | 默认省略；按账户版本启用 |
| Cnt | 可选 integer：10/20/30/40/50；极速版不支持 | P0 可省略，应用自行截取结果数量 |
| Freshness | 可选 string，支持 d1–d30、m1–m12、y1–y5 等 | 不限制长期有效的硬件资料；P1 按确切任务启用 |
| Industry | 可选 string：gov/news/acad/finance；极速版不支持 | P0 不传 |
| Deeplinks | 可选 boolean，仅旗舰版 | P0 不依赖 |

`Site` 对垂直信源不生效，不能仅凭传参认定全部结果来自官网。日期区间在官方正文与示例存在表述不一致，P0 不采用日期区间格式。旧 `FromTime`/`ToTime` 已迁移为 `Freshness`，新图片字段为 `pics`。[迁移公告](https://cloud.tencent.com/document/product/1806/135870)

### 3.2 响应解析

先读取顶层 `Response`，再逐条解析 `Response.Pages` 中的 **JSON 字符串**；兼容对象形态只属应用容错。查询计划与逐次 RequestId 被保留；Version/Msg 当前未持久化，P1可补。页字段包含 title、url、passage、date、site、score；content/pics 依版本可缺，authority_level 仅旗舰版。`score` 是相关性，不是事实正确概率；不能直接转成“可信度百分比”。[A2](https://cloud.tencent.com/document/api/1806/121811)

下例完全是结构测试，不是真实 API 回包：

```json
{
  "Response": {
    "Query": "测试查询",
    "Pages": ["{\"title\":\"测试来源\",\"url\":\"https://example.com\",\"passage\":\"结构测试，不可作为硬件证据\"}"],
    "Version": "standard",
    "RequestId": "MOCK-NOT-A-REAL-REQUEST"
  }
}
```

应用须删除 HTML 标记并以文本展示摘要，校验仅允许 http/https 来源，去重，并让“找到搜索摘要”“人工/程序已核对原文”“测试占位”在数据中可区分。官网结果只能支持摘要直接涉及的型号与属性，不能因为网站权威而推导未出现的性能。

### 3.3 错误与配额

官方业务错误包括 `InternalError`、`InvalidParameter`、`RequestLimitExceeded`、`ResourceNotFound`、`ResourceUnavailable`、`UnauthorizedOperation`。[A1](https://cloud.tencent.com/document/product/1806/130615)

P0 应检查 HTTP 状态及 `Response.Error`，对超时、解析失败、无结果、拒绝查询分别返回显式状态；鉴权失败/服务未开通不重试，限频/暂时服务错误最多有限次退避。真实模式错误不得自动切换成看似真实的 mock；用户必须明确选择 mock 测试。

[API 概览](https://cloud.tencent.com/document/product/1806/121821) 的 QPS 栏为 `-`，未给具体额度，不能解释为无限调用。6000 次是赛事页面的活动权益，实际领取、账户余量及有效期尚未在登录账户中核验。P0 应限制每次调查搜索数并展示调用次数。

## 4. 核验边界与提交闸门

- 已完成：公开规则、侦探要求、字段规格、API KEY 契约的官方文档核验。
- 未完成：登录后的作品表单现场核对、用户账户额度与密钥权限、SearchPro 实际成功调用、三份真实查询素材、真实用户试用、公开分享和作品正式提交。
- 未获用户授权对外发文；本项目仅准备可复制材料。
- 在上述真实调用和素材完成前，项目可以作为清晰标识的 mock P0 运行，但**不可标记“已满足侦探真实查询提交要求”或“已完成参赛提交”**。

登录入口 https://1024.waytoagi.com/contest/submission 的未登录页面只显示账号确认状态；本文表单字段来自公开规则，不声称已检查登录后的实时表单。


## v0.2执行更新

已按官方[腾讯云标准方式](https://cloud.tencent.com/document/product/1806/121802)与[签名v3](https://cloud.tencent.com/document/api/213/30654)新增TC3，使用wsa.tencentcloudapi.com、SearchPro、2025-05-08。仅从环境变量读取SecretId/SecretKey，原Bearer方式保留，两套域名/鉴权不混用。当前已真实连通，并完成三案9次查询，另有1次连通验证，三案截图/报告已生成。旧核验边界中的“真实调用未完成/0份素材”是历史基线，最新见delivery.md与acceptance-v0.2.md。账户额度、正式提交和公开分享仍未核验。
