# 实时显示延迟优化与验证

## 当前状态

候选实现、真实 RK3568 编译、自检及A/B/B/A实测完成。
DMA读回完成到GL绘制返回的平均帧龄降低9.25～12.58ms，
YOLO完成率基本一致，无运行错误。降低帧龄的代价是部分相机显示更新率下降。
最终默认开启版本已安装并启动，PID4701，安装后持续运行验收通过。
原程序保留为 `/userdata/detview-hdmifull/detview-hdmifull.before-latency-fix-20261008`。
设置 `DETVIEW_LATE_LATCH=0` 可在启动时关闭优化。

## 实现

保持24ms发布节拍，在GPU绘制前再次读取最新完整且同generation的可见相机帧。
pixels、tag、sequence、时间戳一并更新并保留共享所有权，上传前释放锁。
已经上传过的同一帧不重复上传。不增加忙轮询，不等待YOLO结果。
DETVIEW_LATE_LATCH=0/1在同一二进制关闭/开启；FPGA位流不变。
YOLO输入转换、InferenceThread、HDMI/视频分析提交等受保护代码逐字节一致，
详见preservation.json。没有降低模型输入尺寸或删减推理功能。

## 验证

四轮A/B/B/A测试二进制SHA256：
`8a32d1ffdb74f1634bed4654c82e1f4e116e37d6863d2785cd63f42d3a9869f0`。
最终安装二进制SHA256：
`eb81db54e9ffac1b943d1f7c576039ebc170b6ca97305328c55d17e35e44c774`。
最终版本仅将未设置环境变量时的开关默认值改为开启，重新编译并通过三项自检。
真实编译无警告，显示ownership/config自检、vision综合自检、MVP round1解码自检通过。
日志及源码身份见build_manifest.json、build_latency.log及三个selftest.log。

原安装版独立基线：去掉前两个窗口后12窗口，CPU帧就绪到GPU上传平均26.060ms，
窗口P95最大46.5ms，无运行错误。该旧指标起点位于CPU复制完成附近。
同二进制正式对照使用新逐相机DMA return→GL upload/draw return指标，
不能拿新指标直接与26.060ms相减。

## 测量边界

软件时间戳不包含曝光、FPGA捕获、GPU异步完成、屏幕扫描或面板响应。
GL draw返回不等于像素已显示，不能声称本报告测得完整摄像头到屏幕延迟。
完整画面延迟需要额外光学对照。各窗口P95最大值不等于合并P95。

正式对照六路真实相机、MVP_accuracy_round1、fullscreen、同HUD/24ms发布配置，
每轮85秒，顺序A1/B1/B2/A2，各取去掉前两窗口后的12个完整窗口。
原始日志与对照汇总将保存在measurement/。

## A/B/B/A实测结果

四轮每轮85秒，去掉前两窗口后每轮约60.4～60.9秒。以下分别合并
A1/A2和B1/B2的计数、时间总和，得到加权均值：

| 相机 | 关闭优化：DMA→绘制返回 | 开启优化 | 降低 |
| --- | ---: | ---: | ---: |
| C1 | 38.13ms | 25.55ms | 12.58ms |
| C2 | 36.14ms | 23.87ms | 12.28ms |
| C3 | 39.08ms | 29.83ms | 9.25ms |
| C4 | 39.40ms | 29.71ms | 9.69ms |
| C5 | 36.08ms | 24.27ms | 11.81ms |
| C6 | 36.03ms | 24.14ms | 11.89ms |

DMA→上传均值分别降低12.50/12.28/9.39/9.73/11.82/11.95ms。
旧CPU就绪→上传指标约26.28→15.57ms（约10.71ms改善），
两个起点不同，不混用相减。两轮B结果一致改善，不能保证所有场景相同。

每轮YOLO完成率：A1 3.829、B1 3.861、B2 3.824、A2 3.859次/秒。
约为A3.844、B3.843次/秒，未观察到完成率下降；protected代码逐字节相同。
这是静态室内主路MVP工作量，不证明所有模型/运动负载绝无资源竞争。
四轮runtime faults为空，六路有帧，DMA错误0。

显示更新率存在取舍：C1/C2约32.3/32.2→28.0/28.6fps，
C5/C6约29.6/29.4→26.7/26.7fps；C3/C4约23.8→24.3/23.8fps。
swap约34.65→33.74fps。采用最新帧跳过旧帧，降低帧龄但未同时提升帧率。
用户优先实时延迟，C5/C6仅要求持续出帧；保留环境开关关闭优化。

原始数据 `measurement/A1.log`、`B1.log`、`B2.log`、`A2.log`；
汇总 `measurement/abba_summary.json`、`measurement/throughput.json`。
本次是RK3568显示取帧策略优化，FPGA位流不变，不归类为FPGA硬件加速。

## 安装后验收

实际安装SHA256与最终构建一致，PID4701保持完整应用运行，late_latch=1。
采集到74条pane统计，六路have=111111，err全部为0，未发现unstable或运行故障。
末段六路采集约44.55/45.11/25.68/25.73/40.45/40.34fps，YOLO继续正常完成。
详见final_acceptance.log及final_acceptance.json。
