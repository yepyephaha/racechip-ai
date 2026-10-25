# v0.1历史验收记录

> 本轮v0.2已完成三案真实查询及48项回归；最新记录见[acceptance-v0.2.md](acceptance-v0.2.md)。以下只保留旧版本基线，不代表当前状态。

日期：2026-10-24，北京时间。验收类型：**本机代码、界面与离线/mock测试**；没有执行真实 SearchPro 查询。

## 已执行

| 检查 | 实际结果 |
| --- | --- |
| Windows运行环境 | Python 3.12.0、Node v22.23.0；独立.venv与package-lock |
| 后端pytest | **37 passed**，耗时约0.5–1秒 |
| 前端构建 | TypeScript + Vite v5.4.21成功；JS约176.86kB，gzip57.25kB |
| 单端口服务 | run.ps1启动FastAPI，GET / 与 /api/health HTTP200 |
| 颜色巡线练习 | 2通过已录入条件、3待核验；RT1062优先，H7保留停产风险 |
| AprilTag练习 | 0通过、5待核验；20 FPS没有实测，不推定满足 |
| 预算功耗冲突 | 0通过、3待核验、2因OpenMV禁用项排除；未知数值不当0 |
| 模式边界 | mock请求数0；live无密钥显式error、请求数0、0个通过 |
| SearchPro传输契约 | MockTransport验证固定端点、Bearer、Query、Pages字符串、错误/部分结果/429和异常响应；**不是联网测试** |
| 浏览器操作 | 载入颜色题→mock分析→候选→可读来源详情；切live→缺密钥错误→全部待核验；切回mock |
| 实际导出 | 浏览器下载MD与JSON，再读取文件确认模式mock、请求0、5候选、18证据、完整输入 |
| 浏览器日志 | QA时error/warn列表为空 |
| 窄屏布局 | 绑定浏览器视口约453×720（截图可见宽438）；文档scrollWidth438，无水平溢出；JSON入口可见 |

pytest有一条当前Starlette TestClient对httpx依赖的弃用提示，不影响37项测试；当前锁定依赖已按实际环境保存。没有为了移除提示更改已通过的运行环境。

截图：[mock工作台](../artifacts/mock-workbench.png)、[真实模式缺密钥错误](../artifacts/live-missing-key.png)。它们是本机真实UI截图，其中mock报告不是实时查询凭据。桌面宽视口未单独捕获，响应式桌面布局经源码和构建检查，不能声称已做跨浏览器全尺寸验收。

机器可读结果在 `artifacts/verification.json`，三份API离线结果为 `artifacts/synthetic-*-mock.json`。实际浏览器下载副本为 `artifacts/mock-ui-export.{md,json}`。源码包 `artifacts/RaceChip-AI-P0-Windows.zip` 由显式文件白名单生成，含源码、构建前端、数据、文档与选定验收材料，排除密钥/依赖/缓存；对应SHA256与清单在package-manifest.json。

## 未验证/未完成

1. SearchPro真实服务连通、账户额度与权限：当前后端未发现密钥。测试夹具与官方文档抓取均不能计入真实查询。
2. 三份真实提问录屏/截图：**0/3**；应接入密钥后按submission-kit重新运行、核对来源并保存真实素材。
3. 硬件接线、运行帧率/准确率、当前人民币报价与完整BOM功耗：未实测；需要用户核验。
4. 评委异地可访问部署、公开社媒分享、登录后的最终表单、报名/正式提交：未执行。localhost不能当异地作品地址。
5. P1：未实现，不作为P0已完成功能申报。

当前交付可以证明P0本机/mock链路可运行；**不能证明已满足侦探真实查询提交条件或已完成比赛提交**。

## 复验

在项目根目录执行 `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`。它不会产生真实搜索，生成新离线记录。真实验收需由前端主动选择真实模式，每次最多3个HTTP尝试；每案单独保存RequestId、查询、来源、结果与截图。按照 [开发方案](development-plan.md) 先补齐P0真实材料，再执行P1。
