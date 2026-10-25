# 硬件数据与练习场景来源

核验日期：2026-10-24。`data/catalog.json` 是本次通过网络读取官方文档后人工整理的静态资料，独立于应用的实时 SearchPro 搜索和 mock 适配器。离线展示目录不能称为“刚刚联网搜索”。本轮没有对任何实体板卡进行供电、刷写、接线、速度或精度测试。

## 数据结构

目录是 JSON 数组。每个候选固定字段为：`id`、`name`、`vendor`、`summary`、`interfaces`、`logic_voltage_v`、`power_w`、`price_cny`、`price_kind`、`capabilities`、`skill_level`、`docs_quality`、`evidence`、`caveats`。

`interfaces` 采用 UART / I2C / SPI / USB / CSI。它表示文档确认的板级连接路径，不保证全部接口可同时使用。Maix Bit 的 USB 是下载/桥接连接；ESP32-S3-EYE 内部 LCD 的 SPI 不当作自由外接 SPI。`logic_voltage_v` 是与主控通信的逻辑电平，绝不从供电电压自动推断。

任务能力采用 `color_tracking` / `apriltag` / `object_detection` / `line_tracking`；`offline_inference` 表示文档中存在本地运行路径，需预先装好模型、固件和依赖。能力支持不等于任务准确率或端到端帧率已经通过测试。

证据结构为 `{id, kind, title, url, claim, field, accessed_at, status, excerpt}`。`verified` 仅表示在本次成功读取的来源里找到了所述内容，不表示已复现硬件行为。`needs_verification` 表示经验待复现或事实未充分核验。官方域名上的论坛帖和官方 GitHub 仓库中的用户 issue 仍归 `community`。

`skill_level`（1 容易，5 困难）和 `docs_quality`（1 低，5 高）是本项目人工判断，用来解释新生上手成本与资料完整度，不能包装成厂家测量指标。排名不能用这些主观分数绕过硬性条件。

## 已读取的官方来源

| 候选 | 官方来源 | 本轮可用结论 | 局限 |
| --- | --- | --- | --- |
| OpenMV Cam RT1062 | [官方产品页](https://openmv.io/products/openmv-cam-rt)、[Image API](https://docs.openmv.io/v5.0.0/library/omv.image.Image.html) | 3.3V I/O、UART/I2C/SPI/USB、随板摄像头与本地图像处理路径 | 官网显示欠货可订购；现货、交期、人民币完整 BOM 未确认；排针未预焊 |
| OpenMV Cam H7 Plus | [官方产品页](https://openmv.io/products/openmv-cam-h7-plus)、[Image API](https://docs.openmv.io/v5.0.0/library/omv.image.Image.html) | 通信接口、I/O 电平与本地图像处理接口有文档支持 | 官方标注已停止常规生产；算法支持不保证本赛题性能 |
| Sipeed Maix Bit K210 | [板卡页](https://wiki.sipeed.com/soft/maixpy/en/develop_kit_board/maix_bit.html)、[官方 PDF](https://dl.sipeed.com/fileList/MAIX/HDK/Sipeed-Maix-Bit/Specifications/Sipeed%20Maix-Bit%20Specifications_EN%20V2.0.pdf)、[旧版 image](https://wiki.sipeed.com/soft/maixpy/en/api_reference/machine_vision/image/image.html)、[KPU](https://wiki.sipeed.com/soft/maixpy/en/api_reference/Maix/kpu.html) | K210 板卡、下载连接、颜色与模型推理路径 | PDF 首次读取成功，但后续分页超时；未填入未完整核验的电平；未用新版 MaixCAM 文档推断 K210 能力 |
| ESP32-S3-EYE v2.2 | [板卡指南](https://docs.espressif.com/projects/esp-board-manager/en/latest/references/boards/esp32_s3_eye.html)、[2026 官方 ESP-WHO 教程](https://developer.espressif.com/blog/2026/05/esp-who-get-started/) | 摄像头、USB 和板上检测路径 | 没有据芯片能力推断可用外接 UART；没有实体编译/刷写验证 |
| Raspberry Pi 5 | [产品页](https://www.raspberrypi.com/products/raspberry-pi-5/)、[GPIO 文档源](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/raspberry-pi/gpio-on-raspberry-pi.adoc)、[相机软件](https://www.raspberrypi.com/documentation/computers/camera_software.html) | 板级接口、GPIO 电平及本地检测软件路线 | 必须另配摄像头等 BOM；官方供电额定值不是实耗；未在 Pi 5 实测 |

Maix Bit 外设依据还包括 [MaixPy v1 UART](https://wiki.sipeed.com/soft/maixpy/en/api_reference/machine/uart.html) 与旧版文档树中的 I2C、SPI。采购/接线前必须读所购修订版的引脚表、复用与电气限制。

## 社区工程记录

1. [OpenMV 论坛：Higher fps from OpenMV Cam H7 plus and MT9V034](https://forums.openmv.io/t/higher-fps-from-openmv-cam-h7-plus-and-mt9v034/5585)。第一人称作者描述取帧、AprilTag 计算与 ROS 发布的不同表现。此记录用于提示测量完整处理链路，并固定传感器、分辨率、曝光、光照、标签尺寸与距离；不把帖内帧率搬成规格。
2. [Espressif ESP-WHO issue #288](https://github.com/espressif/esp-who/issues/288)。第一人称作者描述 Windows 上恢复固件后的 USB 识别异常，讨论并未给出可推广的根因证明。可提示演示前验证固件恢复流程；不能据单例否定整款硬件。

两项都已读到原文，但状态保留 `needs_verification`，因为环境不同且未复现。来源可信度、事实真实性与是否适用于本题是三个不同问题。

## 空值、成本与功耗

五项 `price_cny` 均为 `null`、`price_kind` 均为 `unknown`。没有把美元裸板标价换算成人民币完整视觉套件价，也没有捏造国内现货报价。完整 BOM 至少核对板卡、传感器、镜头、线材、存储、电源和散热，并记录商家、SKU、时间、税运费与可交付性。

五项 `power_w` 均为 `null`。部分厂家页面提供指定状态的电流或电源容量，但它们不能表示统一的整机算法工作功耗。应在明确电源、相机、算法、分辨率和负载后测量平均值、峰值与测试时长。对于预算或功耗硬上限，`null` 必须产生“待核验”；不得当作零、默认满足或从排序分数补齐。

补充供应状态核验：2026-10-24 成功读取 [RT1062 官方产品页](https://openmv.io/products/openmv-cam-rt) 正文，显示欠货可订购；因此加入当前可下单候选，但不称为现货，也不保证截止前收货。搜索结果曾展示不同日期的库存数量，本目录以本次正文为准。同期读取 [OpenMV N6 官网](https://openmv.io/products/openmv-n6) 也显示欠货可订购，其“预计十月初”文案已无法证明当前交期，故本轮未添加 N6。官网可下单、库存充足与按期送达是不同状态。

## 测试场景

`data/scenarios.json` 是三个明确标记的**合成练习题**，非国赛原题、赛事官方题目或用户真实需求。每项为 `{id,title,description,text,constraints,expected}`；`constraints` 包括预算、功耗、必要接口、电平、离线要求和禁用硬件。

默认颜色巡线题不设预算/功耗上限，使官方资料足以核验至少一个候选的已知条件；AprilTag 题用于验证“支持算法”与“达到目标 FPS”有区别；预算冲突题要求未知成本/功耗保持待核验，不允许编造一个能买到的完整方案。

## 在线核验的边界

本轮网页访问工具确实返回了上述正文，包含一次成功的 Sipeed PDF 首页读取；部分错误路径返回不可达，PDF 后续请求超时，均未把失败当作成功读取。来源页面会更新，本项目未留存完整网页归档，也没有在线库存、国内价格、用户实测或实验室性能数据库。文档核验只覆盖每项 `claim`，不代表厂家全部参数均已审计。实时联网搜索是否成功，应由运行时 provider、调用结果与日志显示，不能由这份静态目录代替。


## v0.2真实接入补充

2026-10-24 18:46完成三案真实检索与原文核对。RT1062的io_input_max_v=3.3、H7 Plus=5来自各自产品页I/O耐受说明，不能互相移用，也不能推广到未核验模拟引脚例外或完整双向兼容。该值与logic_voltage_v输出额定值分开；不作为VIN。source_reviews保存本次固定URL摘句匹配、定位、时间、SHA256和未硬件复现状态。病例问题是自拟，API调用和原文读取是真实；48项回归中的输入/响应夹具是合成。历史JSON与截图不假装新查询。
