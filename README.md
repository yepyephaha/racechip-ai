# 赛芯智选 RaceChip AI

## 下载与运行

1. 推荐 Windows 用户下载 [Windows 使用包](https://github.com/yepyephaha/racechip-ai/releases/latest/download/RaceChip-AI-Windows.zip)，解压后安装 Python 3.11+（安装时勾选 Add Python to PATH）。使用包已包含构建好的界面，不需要安装 Node.js。
2. 双击根目录的 `start.cmd`。首次启动会联网安装 Python 依赖；出现服务启动提示后，在浏览器打开 `http://127.0.0.1:8000/`。关闭启动窗口即可停止服务。
3. 不配置 API 密钥也可以打开工作台、查看已保存的完整示例。生成新方案或联网搜索时，需要使用者自行配置自己的模型和搜索凭据；不会使用作者的账号或额度。模型密钥可在页面“模型配置”中填写，搜索凭据按下方“搜索模式与密钥”说明配置。

也可以下载仓库源码 ZIP 或 `git clone` 后双击 `start.cmd`；这种方式首次构建界面还需要 Node.js 20.19+/22.12+。本仓库与使用包不包含 API 密钥、账号密码、真实 `.env`、凭据 CSV 或本机私有配置，`.env.example` 仅提供空白配置字段参考，应用不会自动读取该文件。

面向通用硬件开发的 React/Vite + FastAPI 本机工作台。从一句目标开始，经 TokenHub 上下文决策逐轮提问，形成整套硬件方案、规格与数量清单，再用元宝 SearchPro 补齐商品链接。器件资料、BOM、连接检查、原文问答和工程导出保持可编辑、可追溯。

2026-10-25 视觉升级：按用户选择采用浅色蓝橙竞赛风，增加可点选的起步项目、完整示例预览与操作反馈，覆盖手机和平板。[改动与验收截图](docs/visual-upgrade-2026-10-25.md)。

“证据核验”已改为直接核查任意硬件说法：标准12条/深入18条元宝检索，涵盖厂商资料、用户实际经验、反例与适用条件，读取相关网页/PDF并校对引用。保留来源、读取失败与争议，不再走视觉赛题选型表单。详见[核验方法与边界](docs/evidence-audit.md)。

“方案与BOM”现在可直接填写目标并点击“生成方案并搜索配件”，查看草案与逐件商品搜索后，再采用清单填入BOM。器件搜索的外部结果直接显示在搜索框下，不受本机库匹配数量限制。[操作方法与修复说明](docs/workflow-actions.md)。

## 当前入口：一句话到完整方案

输入“我想做一个循迹小车。”即可开始。系统每次问一个影响方案的问题，按已确认的场景、预算、已有器材和经验继续定位。方案包括机械、感知、控制、驱动、供电、电池与配套充电、线材和装配件；套装包含物写明，减少漏件和重复购买。商品来源统一经元宝，无法确认的 SKU、报价和兼容条件保留待核验。

首页提供“回放新生循迹小车完整示例”。示例中的用户回答是明确标记的模拟输入，问题与方案由真实模型生成，采购来源来自实际元宝检索；回放不新增 API 调用。详见[交互、框架参考和采购规则](docs/guided-flow.md)。

本轮已保存5轮交互与9类配件的实际商品来源。[完整验收](docs/acceptance-v0.3.md) · [离线采购方案](artifacts/novice/index.html) · [浏览器实际下载的工程包](artifacts/novice/complete-hardware-handoff.zip)。具体SKU、到手总价和实物兼容仍需核对。

模型连接使用独立的 `TOKENHUB_API_KEY`、`TOKENHUB_MODEL`（当前验证 `hy4-preview`）和可选 `TOKENHUB_REGION=guangzhou|singapore`。也可在已启动的本机页面点击“模型配置”，用密码字段提交；Key仅保存在后端进程环境，不写浏览器存储或项目文件。模型生成与 SearchPro 搜索不能互相替代。

明确选择的规则演示仅用于离线测试，不是生产对话的后备。模型未配置或调用失败时显示错误，不生成假问题。访谈读取最近38条对话、当前工程、上次方案和近期检索证据，保留实际调用记录。

## 截图识别与持续监测

“证据核验”支持从 PNG、JPG、WebP 图片以及 MP4、WebM 视频中提取文字，再由使用者编辑并选择待核查说法或背景。原始媒体留在浏览器，首次识别需要联网下载 OCR 组件和中英文语言数据；视频最长 5 分钟、最多抽取 5 帧，文件上限 100MB。

“持续盯梢”可以按 6 小时、每天、每 3 天或每周复查同一说法，并显示新来源、判断变化和来源日期。首次核查会立即开始；后续定时任务仅在本机后端运行时执行。任务记录保存在本机，不会随源码发布；桌面提醒需要浏览器保持打开并授权通知。

## Windows 一次安装，单端口运行

需要 Python 3.11+、Node.js 20.19+/22.12+、PowerShell 和网络。当前验证环境为 Python 3.12 / Node 22。

可以在 GitHub 下载 ZIP 后解压，或使用 Git 获取源码：

```powershell
git clone https://github.com/yepyephaha/racechip-ai.git
cd racechip-ai
```

源码包含示例回放及文档引用的验收资料；依赖、构建缓存、本机运行数据和密钥不入库。真实模型与搜索功能需要在本机独立配置自己的 API 凭据，参见下方说明。

解压到其他位置时，把下面的cd路径改为实际项目目录；各脚本会按自身位置定位项目，不依赖固定盘符。

```powershell
cd D:\1024\racechip-ai
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

打开 [本机工作台](http://127.0.0.1:8000/)；[接口文档](http://127.0.0.1:8000/docs)。前端构建文件由 FastAPI 同源提供，不需要同时运行 Vite。当前已完成安装构建，可以直接运行第二条脚本；若端口已被本项目占用，直接打开页面，或 `run.ps1 -Port 8001`。

本机可用 `run.ps1 -SearchCredentialsFile <CSV路径>` 注册腾讯云 SecretId/SecretKey CSV。正常启动脚本随后自动读取原文件；用户配置目录只保存来源路径，不复制密钥、不放入源码包。已有显式搜索环境变量时优先使用环境变量。原CSV需保留在原位置，换电脑或换项目目录后重新注册。TokenHub仍独立配置。

开发时：一个终端 ` .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload`，另一个终端进入 `frontend` 后 `npm.cmd run dev`；Vite 将 `/api` 代理到 8000。

## 搜索模式与密钥

- `Mock 测试`：合成检索记录，**0 次联网请求**；不会冒充元宝搜索。人工核验的固定硬件资料与 mock 记录分开展示。
- `真实搜索`：后端按凭据选择官方Bearer或TC3签名端点，每次调查最多 3 个查询，失败即停止。没有密钥、鉴权失败、限额、超时或解析错误均显示真实状态，不切换 mock。
- 密钥只从 **后端进程环境变量 `TENCENTCLOUD_WSA_APIKEY` 或 `TENCENTCLOUD_SECRET_ID`/`TENCENTCLOUD_SECRET_KEY`** 读取；不要放进 `VITE_*`、源码、截图或聊天。本项目不自动加载 `.env`。

在启动后端的同一 PowerShell 会话中，可隐藏输入密钥：

```powershell
$racechipSecret = Read-Host 'SearchPro API Key' -AsSecureString
$racechipCredential = New-Object System.Net.NetworkCredential('', $racechipSecret)
$env:TENCENTCLOUD_WSA_APIKEY = $racechipCredential.Password
Remove-Variable racechipSecret,racechipCredential
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

重启服务后，健康接口只返回 `search_configured: true/false`，不回显密钥。前端主动选择真实搜索再运行。若原服务已启动，先在它的终端按 Ctrl+C。服务 API KEY 的 Bearer 方式与腾讯云 SecretId/SecretKey 的 TC3 签名方式不同，不能混用；详见[运行与配置](docs/deployment.md)。

## v0.2 保留的单项证据核验

粘贴赛题文本 → 编辑预算/功耗/接口/电平/离线/禁用项 → 拆成 3 条资料查询 → 官方固定证据与实时检索线索分层 → **通过 / 待核验 / 排除** → 查看理由、风险与原文出处 → 导出 Markdown 和 JSON。

默认库 5 款候选、18 条来源证据（含 2 条社区工程经验）。价格和统一工况功耗均保留未知。3 道演示题均为自编练习题，不是真实电子竞赛题。单项核验解析器为确定性规则；首页通用需求对话另行使用真实模型API。

`通过` 只表示满足**已录入且已建模的条件**，仍需验证实际帧率、精度、供货与完整系统。预算/功耗证据缺失不能通过；性能要求和整机条件超出 P0 核验范围时标待核验。实时模式只有搜索完整成功且发现对应候选官方域线索，才允许通过；搜索摘要不能自动改写硬件参数。

## 验证与材料

```powershell
cd D:\1024\racechip-ai
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

验收运行不会调用真实 SearchPro，输出 `artifacts/verification.json` 和三份 `*-mock.json`。测试里的 HTTP MockTransport 是传输契约测试，不是联网凭证。

- [完整硬件方案与采购流程](docs/guided-flow.md)
- [方案生成与器件搜索操作](docs/workflow-actions.md)
- [证据核验方法与边界](docs/evidence-audit.md)
- [运行与配置](docs/deployment.md)
- [接口与数据契约](docs/api.md)
- [真实硬件数据来源](docs/data-provenance.md)
- [实际验收结果](docs/acceptance.md)

公开仓库和 Windows 使用包仅包含应用源码、运行与使用文档、测试及应用示例。比赛提交说明、演示讲稿、社媒草稿和内部调研计划保留在本地，不属于分发内容。当前程序默认运行在本机，不自动部署到公网；硬件兼容性、实物效果和实时采购信息仍需按实际条件核对。

标准SecretId/SecretKey请运行 `powershell -ExecutionPolicy Bypass -File .\scripts\run-tc3.ps1` 隐藏输入。见[运行与部署交接](docs/deployment.md)。
