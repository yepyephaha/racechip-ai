# 运行与部署交接

当前实际运行：http://127.0.0.1:8000/ 。只供本机访问，未创建收费云资源或对外发布。

2026-10-25 已恢复元宝搜索：用户提供的CSV经TC3真实调用成功，1次请求返回10条结果。当前模型连接保留，搜索与模型同时配置。`scripts/run.ps1`现支持 `-SearchCredentialsFile <CSV路径>`；注册后正常启动会读取原CSV。来源引用保存在当前Windows用户的项目专属配置目录，只含路径，密钥不复制到源码、引用配置或交付包。以后原文件移动时需重新注册；TokenHub仍采用独立的进程内配置。

Windows在项目根目录执行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1` 安装构建，再执行 `powershell -ExecutionPolicy Bypass -File .\scripts\run-tc3.ps1`。后者隐藏输入SecretId/SecretKey，仅设置进程环境，退出后不持久化；已有环境变量时不再输入。原服务占8000时先在原终端Ctrl+C，或传`-Port 8001`。聊天中暴露的凭据应由本人轮换后重新配置。

无密钥也可查看三份历史真实实录。双击 `artifacts/submission/index.html` 不需Python即可查看证据索引；新查询需有效SearchPro权限。

Dockerfile已准备，尚未实际构建或部署。示例只引用本机环境变量，不把密钥写进镜像：

```powershell
docker build -t racechip-ai:0.2 .
docker run --rm -p 127.0.0.1:8000:8000 -e TENCENTCLOUD_SECRET_ID -e TENCENTCLOUD_SECRET_KEY -e SEARCHPRO_AUTH_MODE=tc3 racechip-ai:0.2
```

上述仍是本机映射。公开托管需选实际平台，完成后用另一设备核验HTTPS、实录和真实搜索，再填写真实URL。现有源码包与材料可按官网“链接或文件”的实际槽位提交；登录后字段由本人核对。
