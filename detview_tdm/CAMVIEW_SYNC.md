# 按新版 camview 同步的显示优化

后续优化顺序、测量方案与验收条件见 [性能优化计划与TODO](TODO.md)。

新版 camview 源码位于板端`/root/ov5640/camview_display_optimized/`，本地留档在`logs/tdm_camview_sync/current_camview_display_optimized/`。对比后保留 detview 已有的 DMA 优化：六路独立采集线程、一次 DMA 读取帧和尾部标签、独立 RX 槽、AArch64 拷贝及有界帧邮箱；这些路径没有换回 camview 的逐帧隐式共享赋值，避免采集线程在下一帧写入时发生 QByteArray detach。

本次修改同步新版 camview 的显示侧策略，并移除旧显示链路的冗余拷贝：

- 每路相机使用独立RGB565 GPU纹理，支持1–3槽轮换。实际运行的camview设置`CAMVIEW_TEXTURE_RING=1`和`CAMVIEW_SWAP_INTERVAL=0`，因此detview默认也使用单槽并关闭垂直同步；可用`DETVIEW_TEXTURE_RING=3`测试轮换、`DETVIEW_SWAP_INTERVAL=1`恢复垂直同步。关闭同步允许更快交换，但可能产生画面撕裂；这两个参数需要按显示环境选择，不能只照搬源码默认值。
- 每路RGB565帧通过拥有像素的`QByteArray`直接交给有界显示邮箱，取消`LatestFrames → cam565 → composite → uploadTile`的复制、整幅detach和拆格打包。采集复用缓冲仍被显示快照共享时，先分配未初始化的可写缓冲，再由DMA像素拷贝完整覆盖；不复制即将被覆盖的旧像素。
- 保持按变化相机上传，GLES2直接读取连续640×480 RGB565数据，未变化相机不产生上传。
- 监看模式改为六路独立纹理绘制；单路模式只绘制选中的相机，仍由 GPU 负责等比缩放。
- HUD使用CPU位图保证Mali字形清晰，但通过持久GL纹理显示，取消窗口上的QPainter GL绘制。更新范围缩到顶栏、底栏、相机标签、选中边框、检测框线及目标标签；仅启用车道掩码时覆盖完整选中相机区域。移动或消失目标的旧区域先清除再上传，避免残影。动态检测框随结果更新，帧率标签与设置诊断最多每300ms刷新。检测TTL及深度缓存到期也会触发覆盖层更新。使用预乘alpha混合与QRegion互斥裁剪，避免小窗口或双目预览重叠时重复混合。
- 顶点使用按槽缓存的持久GL缓冲，只在几何变化时更新；所有相机和HUD纹理先上传，再清理窗口帧缓冲并绘制，与新版camview的顺序一致。
- 视频源继续使用单纹理路径；设置页、检测框、双目预览和帧率统计行为保持。

显示邮箱保留来源代号、各路帧序号和未消费变化掩码合并规则，检测坐标仍由相机编号映射，均不依赖CPU合成图。显示自测改为检查原始帧快照所有权、覆盖合并与来源切换。`DET_DUMP_COMP`仅在显式诊断时合成一次PNG，正常显示不做合成。采集DMA没有重复实现，也没有修改FPGA寄存器或内核驱动。

相机模式、选中路与来源代号在配置锁下取得同一份快照，发布时再次核对；切换或暂停期间生成的旧布局不会以新的来源代号发布。

## 验证

最终板端构建和`--vision-selftest`退出码均为0，编译日志无warning；`TRACKER_SELFTEST_PASS`、`CAMERA_DMA_SELFTEST_PASS`、`FRAME_METRICS_SELFTEST_PASS (208 checks)`、`VISION_SELFTEST_PASS`全部通过。最终构建、自测、原始帧率与资源日志见[直传验证目录](../logs/tdm_camview_direct/)。

性能验收采用顺序独占：记录原camview启动参数和12秒资源，Q键正常关闭，启动detview记录30秒资源和统计，然后核对六宫格、设置页、单路、返回总览、暂停和恢复截图；detview退出后恢复原camview。脚本为[validate_detview_direct.py](../scripts/validate_detview_direct.py)，汇总为[analyze_detview_direct.py](../scripts/analyze_detview_direct.py)。测试期间场景变化，因此这些数字是运行观察，不是固定帧回放的严格对照。各项一秒滑动窗范围不等于全程吞吐均值，`paint_new_fps`不代表屏幕扫描率或GPU完成率。

着色器的顶点/片元`vTex`统一为`mediump`，避免严格GLES2实现因精度不一致而链接失败。HUD区域高度按实际字体度量计算，目标相机裁剪与待更新区域取交集；较大字体不会越过清理区域。实板分页和截图检查使用1920×1080，小窗口、高DPI、视频来源与实物双目测距尚未单独验收。

## 最终实板结果

最终测试进程为detview PID29747，脚本记录`DIRECT_UI_PASS`、`DETVIEW_EXIT 0`，并恢复camview PID29817。监看、设置、单路、返回六路、暂停和恢复均留下截图，监看/单路截图中相机标签、追踪框线和文字正常。汇总见[summary.json](../logs/tdm_camview_direct/summary.json)。

| 指标 | 最终detview观测 |
| --- | --- |
| C1–C6采集率，采集日志窗口均值 | 43.12 / 44.58 / 25.73 / 25.74 / 40.34 / 40.31 fps |
| 新画面率，已记录一秒窗口范围 | 19–27 fps |
| 总绘制率，定期累计统计快照均值 | 22.17 fps |
| 绘制耗时，定期累计统计快照均值 | 27.68 ms |
| CPU平均占用，启动8秒后资源样本 | 2.91核；camview同次资源采样为2.03核 |
| 最大RSS | 163.44 MiB；camview为124.66 MiB |
| NPU负载，启动8秒后样本均值 | 2.41%；识别与模板追踪开启 |
| 采集错误 / 不稳定帧 / GL错误 / 新增内核错误 | 0 / 0 / 0 / 0 |

前轮旧detview的新画面窗口约16–18fps，此次显示吞吐有所改善，六路采集率也更接近camview；场景和目标数变化，不能把差值当作固定场景下的提升比例。同次camview近期日志的最新`swap_fps/ uploaded_fps`为39.48，detview仍有明显显示开销，未达到camview吞吐。单路截图瞬时新画面标签为34fps，未作长时间单路均值测试。

最终`main.cpp` SHA256为`4e9ffa6fa2ae094cc1e2c26f46cb9f0a6798c540e455dfda058ae256203dd882`。可执行文件位于板端隔离目录`/userdata/linaro/detview-vision-work/build/detview`。

## 后续TODO推进

已修正重复空掩码、相同检测与预览导致的HUD失效，设置页按revision/布局刷新，监看页保留TTL和300ms指标刷新。新增可关闭的固定桶分段墙钟、HUD/相机工作量、GUI延迟、快照替换和交换计数；实现C1/C2与C5/C6双组独立状态。最终构建无warning，自测216项metrics及刷新/追踪/DMA/双组融合通过。

正常模式10秒预热、60秒不截图采样，11个完整统计窗55.699秒的新画面23.304fps，回调21.269ms。按耗时和，HUD栅格/打包/上传约占绘制墙钟55.4%，相机上传38.5%；当前应优先优化HUD真实区域与调用负担。计时包含GL等待；场景与前轮不同，不能据数字变化认定代码增益。完整矩阵/三轮与30fps目标仍未达成。

实板两组未标定预览、C1/C5切换、设置与暂停恢复通过，未输出可信米数。测试结束恢复camview PID31185并独占设备。隔离构建位于`/userdata/linaro/detview-todo-work/build/detview`；完整数据、源码/二进制哈希及验证边界见[TODO验证记录](TODO_VALIDATION.md)。
