## 2026-10-07 MVP-R1 与识别框防闪烁

当前版本支持矩形640×480模型、MVP-R1绑定哈希的类别阈值、共享/独立UFLDv2车道点，以及默认三次检测确认显示框。全速视频漏检缓冲180ms；实际漏检超过缓冲后需重新确认。`--no-temporal-filter`用于显示过滤对照，模型阈值与推理调度不变。

完整发布、板端程序和性能证据见[发布记录](../releases/detview_temporal_20261007/README.md)。源码详见[时序过滤](README_TEMPORAL.md)、[MVP配置](README_MVP.md)及[MVP-R1配置](README_ROUND1.md)。已通过最终118项行为检查及八组板端自检。常驻预览不自动截图。

# detview YOLO 时分复用

已融合仅车辆CPU模板追踪和双目测距：NPU默认间歇检测，帧间匹配更新车辆ID与位置；行人、斑马线和交通标志保留NPU检测。双目复用现有采集帧，显式指定两路才启用。使用、参数与有效条件见[识别＋追踪＋测距](VISION.md)。

本目录基于四路 `detview` 扩展为 **六路**采集，并支持 2–4 款 YOLO 检测模型轮换。一个推理线程顺序使用各模型的 RKNN 上下文，每个模型只加载一次；相机或视频解码继续提供最新帧，推理忙时覆盖待处理帧，避免积压和重播旧画面。内核 PCIe 驱动与 DMA 地址协议不变（地址表与运行版 camview 六路版一致）。

界面是**单个顶层 `QOpenGLWindow`**（camview 同款 GPU 路径，无独立工具栏窗口）：相机原始 RGB565 合成后直传纹理，缩放/letterbox 在 Mali 上完成，工具栏、追踪统计和双目状态画在HUD，操作走键盘。

## 使用

```sh
./detview --rotate-model zebra-rk3568-raw-dfl6,wb_v4_combo
./detview --fullscreen --rotate-model zebra-rk3568-raw-dfl6,wb_v4_combo
./detview --fullscreen --camera 1 --rotate-model zebra-rk3568-raw-dfl6,wb_v4_combo
./detview --video demo.mp4 --rotate-model zebra-rk3568-raw-dfl6,wb_v4_combo
# 480p本地视频循环调试，仅车辆追踪；三分类定位质量优先候选
./detview --video demo_480p30.mp4 --video-loop --model zebra-merged-v3-rk3568-raw-dfl6 --fullscreen --tracker-debug --detect-interval-ms 250 --detect-min-ms 250 --track-interval-ms 33 --track-template-side 48
# 定时结束（短测）: --duration 30；到点自动截一张 GL 帧缓冲: --shot 300
# 无人值守自愈（连续 DMA 失败自动退出并重启）: sudo bash run_detview.sh --fullscreen --rotate-model a,b
```

键盘：`1-9` 切单模型 | `R` 轮换开关（集合由 `--rotate-model` 给出，未给时默认全部非 lane 检测模型最多 4 款）| `V` 相机（C1–C6 单路 / 6 路 3×2）| `C` 框格式 | `+/-` 置信度 | `S` 截屏到 `/userdata/detview_shots/` | `P`/空格 暂停 | `F` 全屏 | `H` 帮助 | `Q`/Esc 退出。

`--rotate-model` 传逗号分隔的唯一文件名子串，每个子串必须只匹配一款已扫描模型。`--video` 也接受网络 URL，由 `ffmpeg` 解码为 640×480 RGB，再 letterbox 到 640×640；视频模式不访问 PCIe。默认是 **6 路 3×2** 显示并对 C1 推理。`--shot N`（第 N 秒抓一张 GL 帧缓冲，用于远程/无人值守留证）、`DET_DUMP_COMP=1`（把合成缓冲原样存 `/tmp/det_comp.png`，用于分辨"合成错"还是"显示映射错"）。

`--video-loop` 仅接受本地视频文件。`DETVIEW_VIDEO_FPS` 限制发布帧率，默认30，合法1–60；原视频更慢时保持原速率。暂停停止解码子进程，恢复不追赶积压时间。`--tracker-debug` 输出车辆ID、NCC、预测状态及检测源帧日志。道路视频实测与局限见[视频验证](VIDEO_VALIDATION.md)。

## 采集与显示

采集结构与运行版 camview 六路版一致：**每路一个采集线程**按帧标签轮询（10ms 一档）并 DMA 读整帧，六路共用一条 DMA 通道（读写串行化）；显示线程按“代（gen）变化 + 默认 33ms 节流”把有变化的格子**按 RGB565 原样搬**进 **3×2 合成缓冲（1920×960）**（`compStride = 640*2`，所以一格是连续的一块，一次 `memcpy` 即可，不再逐像素转 RGB888），缓冲双缓冲复用、`QImage` 只做包装（`Format_RGB16`），**不做每帧分配**。

显示是**单个顶层 `QOpenGLWindow`**：`glTexImage2D(GL_RGB, GL_UNSIGNED_SHORT_5_6_5)` 直传 RGB565 合成帧（3.7MB），letterbox 与缩放由 GPU 完成；检测框用 QPainter 画矩形，所有文字（每路 fps 标签、模型/相机/置信度行、框标签）都先画进小位图缓存再贴（直接在 GL 窗口上画文字会被 Mali 的字形图集画花，camview 已踩过）。板端没有合成器（`_NET_WM_CM_S0` 不存在），`QOpenGLWidget` / `createWindowContainer` 会闪，因此只用**顶层** GL 窗口这一种形态。

HUD 的每格 fps 标签**不要**再用“整窗 ARGB 位图 + 每帧 drawImage”的写法：那等于每帧上传 1898×955×4≈7.3MB，实测 `paintGL` 多花 10ms 以上；现在只贴几张缓存小位图。

环境变量：`DETVIEW_MIN_MS` 覆盖显示节流（默认 33ms，0 = 不限速）。调大可在推理与显示之间更偏向推理。`DETVIEW_GEO=1` 每秒打印一行窗口几何（`win= / dpr= / screen=`）。

启动参数 `--fullscreen` 直接全屏（等价于运行后按 `F`）。板端 XFCE 的“窗口缩放”会把 Qt 逻辑尺寸和 X 实际窗口拉开（例如 1.25x 时 Qt 认为 1920×1080 的窗口只有 1536×864），全屏时画面只能铺满左上角，因此程序启动时固定 `QT_SCALE_FACTOR=1` 并关闭自动屏幕缩放；如确需缩放可用同名环境变量覆盖。

### 帧率口径

- 工具栏：`轮换 N 款 | 整体 X fps | <短名> a  <短名> b fps | 本次 M ms | 检测 Z`。
- **整体 fps**：1 秒窗口内**完成推理的次数 / 实际跨度**（任意一款完成即计一次），即轮换整体吞吐。
- **每款 fps**：同一窗口内按模型分别计数，是该款自己的窗口帧率。严格轮转时 `整体 ≈ 各款之和`。
- 不能用“相邻两次完成的时间戳求倒数”：GUI 线程每帧绘制十几毫秒，会把排队的完成信号挤在一起处理（相邻时间戳可能只差 1ms），会算出几百 fps 的假值，因此改用窗口计数。
- `本次 M ms` 是单次推理的墙钟耗时（`rknn_inputs_set → run → outputs_get` + DFL 解码/NMS），不参与帧率计算。

**提交不跟显示节流走**：推理输入由“选中那一路”的采集线程在读到新帧后直接提交（`setInferPane`），与显示循环的 `DETVIEW_MIN_MS` 无关。早前把提交放在显示循环里，实测把显示节流放到 200ms 时整体吞吐会跟着掉到 5.9/s。

**单路模式会停采其余五路**（`--camera N` 或按 `V` 切到 C1–C6）：单路时其余采集线程不再轮询标签、不再发 DMA。改为 GL + RGB565 + 小位图 HUD 之后实测 **6 路 3×2：显示 25.8–26.0 fps、每路采集 24–26 fps、paint ≈24ms**——此时显示已由相机/DMA 速率决定，不再是绘制。

**缩放走 GPU**：合成帧按原始尺寸上传纹理，letterbox 由着色器完成。当前使用拥有像素的QImage与最新画面邮箱，`[panes]`不再输出`rga=`；单格纹理上传会先打包连续行。下文历史性能记录来自融合前的构建。

### 偶发 DMA 超时与自愈

驱动的 `pango_cdev_open` 每次打开设备都会清 `g_dma_flag` 等状态，所以“退出进程 + 重新打开”就等于恢复，**不需要 `rmmod/insmod`**。本程序据此自愈，两条独立的判据都会 `exit(3)` 硬退出（fd 关闭），配 `run_detview.sh`（`flock` + 3 秒后重启）实现无人值守：

- **连续 6 次 ioctl 失败**（`PangoDev::ioctlTmo` 计数）——丢 MSI 后驱动把 `g_dma_flag` 停在 1 的典型表现；
- **60 秒没有任何新帧**（控制器里的看门狗，`DETVIEW_NOFRAME_MS` 可覆盖；暂停时不计时）——覆盖“相机停摆”和“ioctl 被驱动的 `_sem` 卡住、失败计数永远不推进、应用挂着不退”这两种情况。

`run_detview.sh` 还有**第二阶段恢复**：连续 3 次失败（说明不是单次丢 MSI，而是 FPGA 位流复位/PCIe 侧失步）时，自动执行项目文档规定的 `rmmod` → `/sys/bus/pci/devices/0002:21:00.0/remove` → `rescan` → `insmod`。**这一步是必需的**：位流复位后不做 PERST/重扫，一切总线主控 DMA 会静默死锁（MMIO 正常，极具迷惑性），此时只重载驱动、只重启应用都无效——2026-09-29 晚实测确认（重烧位流 + 重扫后立刻恢复：显示 26.2–26.6 fps、超时 0）。

驱动**有意**不在 MSI 超时路径清 `g_dma_flag`（见 `driver_pango/board_driver/DRIVER_FIX_20260926.md`：正在进行的 FPGA 传输还在时清标志会让第二个描述符与第一个重叠），所以一次丢 MSI 只废掉当前进程实例，重启即恢复。

每款模型保留最近一次检测框，框标签带短名；超过 2 秒未更新的隐藏。状态栏同样以“整体 X fps | …每款耗时/检测数/该款 fps/结果年龄”呈现。LinkNet 分割模型仍走单模型路径，不参与轮换。

## 验证

```sh
qmake detview.pro && make -j2
QT_QPA_PLATFORM=offscreen ./detview --dfl-selftest
QT_QPA_PLATFORM=offscreen ./detview --lane-selftest
QT_QPA_PLATFORM=offscreen ./detview --rotate-selftest image.ppm zebra-merged-v3-rm8,tt100k-anneal-c12
```

板端自检：`DFL_SELFTEST_PASS`、`LANE_SELFTEST_PASS`；静态图轮换自检两款各 40 次、四款各 20 次严格轮转，未重新初始化上下文。

### 实测记录

- 单顶层 GL 窗口 + RGB565 合成（`GL_UNSIGNED_SHORT_5_6_5`）+ 小位图 HUD（2026-09-29）：3×2 六路 + 两款轮换（`zebra-rk3568-raw-dfl6` / `3cls-wb_v4_combo`），`have=111100`、`err=0`、`rga=1`；**显示 25.8–26.0 fps**、每路采集 24–26 fps、整体推理 24–29 fps（每款 10.5–11 fps）、`paintAvg ≈24ms`。对照：改之前（CPU 合成 RGB888 + 每帧整窗 ARGB HUD）显示 21–22 fps、paint ≈31ms；纯 camview（无检测）显示 23.9 fps。
- **20 分钟长稳 soak**（2026-09-30，FPGA 重烧位流后的干净状态，守护脚本运行）：806 个 1 秒样本，**全部 `have=111100`、全部 `err=0/0/0/0/0/0`**；显示 **min 25.6 / avg 26.27 / max 26.9 fps**，每路采集 18–26 fps，整体推理 min 18.2 / avg 22.5 / max 27.0 fps，`paintAvg` min 16.5 / avg 17.75 / max 19.2 ms。期间自愈**自动触发 12 次**（`[recover]`）、守护重启 20 次、**第二阶段 PCIe 重扫+驱动重载 4 次**，每次都自行恢复、无需人工 `rmmod`。注意 `--duration` 是**每个实例**计时，自愈重启会顺延总时长（想做定时 soak 请自行按时间停止）。
- 4 路时期（BAR0 8K/BAR1 4K/BAR2 4K）：Quad + 两款轮换 70s，`have=1111`、`err=0/0/0/0`，显示 23.13 fps、轮换吞吐 17.77 次/秒（每款 8.89），单帧 zebra 43.4ms / TT100K 63.1ms，paint 2.29ms。
- 6 路时期（同一位流扩展，camview 六路地址）：3×2 + 两款轮换，显示 **19–21 fps**、`have=111100`（C1–C4 有帧，C5/C6 无数据，`err=0`）、每路采集 21–23 fps，整体推理 **15.4–16.5 fps**、每款 7.7–8.2 fps，单帧 44/63ms，paint 17ms（`rga=1`）。
- 单路 C1 + 两款轮换：采集 **28–29 fps**、显示 **22–24 fps**、paint **13.9ms**、整体推理 **16.5 fps**。推理线程探针（`DET_BENCH` 下的 `[infer-diag]`）：平均运行 53ms + 平均等帧 7ms；按单次均值 52ms 推算的轮换上界约 19.2/s，剩余差距来自每轮约 7ms 的管线开销。
- 位流与驱动必须匹配：当前 64K-BAR0 的位流会让 `pango_pci_driver` probe 失败（`-EINVAL`）且 ioctl 触发内核 Oops；实例被强杀后驱动会残留 TX buffer（dmesg `TX Buffer already allocated!`），需 `rmmod/insmod` 或重启才能再起。正式 `/root/npu/detview/detview` 未替换。


### 白板三分类 V8/V9（新压缩模型，2026-09-30）

| 模型 | 纯 NPU `run` | 纯 NPU run+io | 应用内单次 | 应用内吞吐 |
|---|---|---|---|---|
| V0 base | 26.42 ms | 30.43 ms | ~40 ms | 21.1 fps |
| V2 rep1 | 25.12 | 29.23 | — | 21.4 |
| **V8**（去 backbone P2/4 C2f） | **20.73** | 24.65 | **33–36 ms** | **27–32 fps** |
| **V9**（轻量 P5） | 24.30 | 28.20 | 38–42 ms | 24–26 fps |

- **耗时由激活访存量决定，不是层数**：V8/V9 层数 55/52 几乎相同，但 V8 去掉的是 160×160 高分辨率阶段（逐层归因：160×160 桶 4380→1203us，占其总收益 52%），总访存 −22.7% → 耗时 −28.4%；V9 只去掉 20×20（P5）低分辨率层，访存 −9.3% → −12.0%。
- 单层最贵的始终是输入层 `model.0`（640→320，~2.1ms，占 9–12%）；80×80（33–38%）+ 40×40（24–27%，P3/P4 头）两个变体都没动。
- 完整报告与逐层原始日志：WebDAV `yolo_project/whiteboard_3cls_v8_v9/profiling_20260930/`。

### 应用内 vs 纯 NPU 的差距（`DET_BENCH` 分段，V8）

| 段（ms） | 6 路 | 单路 C1 | 无并发（静态图 selftest） |
|---|---|---|---|
| prep 输入拷贝 | **0.00**（已优化：直接喂相机线程的 640×640 缓冲） | 0.00 | 2.2（非 640×640 走 letterbox 路径） |
| set `rknn_inputs_set` | 1.3–1.6 | 1.0 | 0.6 |
| **run `rknn_run`** | **27.9–28.5** | 26.2 | 22.9 |
| **get `rknn_outputs_get`（want_float 反量化）** | **4.7–5.7** | 4.9 | 3.1 |
| query（6×`rknn_query`） | 0.3 | 0.3 | 0.3 |
| decode（DFL+NMS） | 1.1–1.3 | 1.2 | 1.1 |

1. 应用内单次 ≈ 纯 NPU `run+io`（24.65）+ ~1.5ms → **推理路径本身没有浪费**；主要差距来自**并发**（6 路采集 + 显示把 `run` 22.9→28、`get` 3.1→5.3）。
2. **输入按 INT8 直传是慢路径**（`inputs_set` 1.4→16.9ms，整体 +58%），必须走 UINT8；`DET_INT8_IN=1` 可复现该对照。
3. 待做优化（按收益排序）：`get` 改 int8 输出 + 解码内联反量化（~1.5–2ms）；输入/输出改 `rknn_create_mem`/`rknn_set_io_mem` 零拷贝（可省 `set`，并可能收回 `run` 的 ~2.2ms 差）；`rknn_query` 属性在加载时缓存（0.3ms）。
## 双目测距原型

独立 C++ demo 位于 [stereo_demo/](stereo_demo/README.md)，保留合成双目、离线图片、FPGA双路输入以及ROI视差测距功能；其算法也已接入TDM目标。真实相机配对、标定参数和同步验证待提供；未标定或实时同步配对未确认时不输出实物米数。
