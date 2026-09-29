# detview YOLO 时分复用

本目录基于四路 `detview` 扩展为 **六路**采集，并支持 2–4 款 YOLO 检测模型轮换。一个推理线程顺序使用各模型的 RKNN 上下文，每个模型只加载一次；相机或视频解码继续提供最新帧，推理忙时覆盖待处理帧，避免积压和重播旧画面。内核 PCIe 驱动与 DMA 地址协议不变（地址表与运行版 camview 六路版一致）。

## 使用

界面点击“选择轮换模型”，勾选 2–4 款 YOLO 检测模型，再按“轮换”；点击取消后回到当前单模型。命令行可传逗号分隔的唯一文件名子串。子串必须各自只匹配一款已扫描模型，避免误选：

```sh
./detview --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --fullscreen --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --fullscreen --camera 1 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --video demo.mp4 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --video /dev/video0 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
# 定时结束，用于短时测试：追加 --duration 30
```

`--video` 也接受网络 URL，由 `ffmpeg` 解码为 640×480 RGB，再 letterbox 到 640×640。视频模式不访问 PCIe；不带 `--video` 时用 FPGA/PCIe 采集。默认是 **6 路 3×2** 显示并对 C1 推理；Cam 下拉可选 C1–C6 单路（单路时对该路推理），键盘 `V` 依次循环。切换相机时清除旧结果。

## 采集与显示

采集结构与运行版 camview 六路版一致：**每路一个采集线程**按帧标签轮询（10ms 一档）并 DMA 读整帧，六路共用一条 DMA 通道（读写串行化）；显示线程按“代（gen）变化 + 默认 33ms 节流”把有变化的格子转成 RGB888 写进 **3×2 合成缓冲（1920×960）**，缓冲双缓冲复用、`QImage` 只做包装，**不做每帧分配**。

显示走**普通 QWidget/QPainter**（不依赖 GL，也不需要合成器）：每帧一次等比 `drawImage` + 检测框/车道掩码叠加。板端没有合成器运行（`_NET_WM_CM_S0` 不存在），`QOpenGLWidget` 与“顶层 `QOpenGLWindow` + `createWindowContainer`”都会出现陈旧区域/双份绘制（画面闪、留残影），因此放弃 GL 路径。

环境变量：`DETVIEW_MIN_MS` 覆盖显示节流（默认 33ms，0 = 不限速）。调大可在推理与显示之间更偏向推理。`DETVIEW_GEO=1` 每秒打印一行窗口几何（`win= / dpr= / screen=`）。

启动参数 `--fullscreen` 直接全屏（等价于运行后按 `F`）。板端 XFCE 的“窗口缩放”会把 Qt 逻辑尺寸和 X 实际窗口拉开（例如 1.25x 时 Qt 认为 1920×1080 的窗口只有 1536×864），全屏时画面只能铺满左上角，因此程序启动时固定 `QT_SCALE_FACTOR=1` 并关闭自动屏幕缩放；如确需缩放可用同名环境变量覆盖。

### 帧率口径

- 工具栏：`轮换 N 款 | 整体 X fps | <短名> a  <短名> b fps | 本次 M ms | 检测 Z`。
- **整体 fps**：1 秒窗口内**完成推理的次数 / 实际跨度**（任意一款完成即计一次），即轮换整体吞吐。
- **每款 fps**：同一窗口内按模型分别计数，是该款自己的窗口帧率。严格轮转时 `整体 ≈ 各款之和`。
- 不能用“相邻两次完成的时间戳求倒数”：GUI 线程每帧绘制十几毫秒，会把排队的完成信号挤在一起处理（相邻时间戳可能只差 1ms），会算出几百 fps 的假值，因此改用窗口计数。
- `本次 M ms` 是单次推理的墙钟耗时（`rknn_inputs_set → run → outputs_get` + DFL 解码/NMS），不参与帧率计算。

**提交不跟显示节流走**：推理输入由“选中那一路”的采集线程在读到新帧后直接提交（`setInferPane`），与显示循环的 `DETVIEW_MIN_MS` 无关。早前把提交放在显示循环里，实测把显示节流放到 200ms 时整体吞吐会跟着掉到 5.9/s。

**单路模式会停采其余五路**（`--camera N` 或 Cam 下拉选择 C1–C6）：单路时其余采集线程不再轮询标签、不再发 DMA。实测单路 C1 采集 28–29 fps、显示 22–24 fps、paint 13.9ms；6 路 3×2 时采集 21–23 fps、显示 19–21 fps、paint 17ms。

**缩放交给 RGA**：合成缓冲放 dma-heap，按控件内容尺寸做 `imresize`（单选时先 `imcrop` 该格），控件只做 1:1 贴图。同尺寸 Qt 缩放要 31ms，RGA 实测 5ms 且不占 CPU；dma-heap 不可用时自动退回 Qt 缩放。

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

- 4 路时期（BAR0 8K/BAR1 4K/BAR2 4K）：Quad + 两款轮换 70s，`have=1111`、`err=0/0/0/0`，显示 23.13 fps、轮换吞吐 17.77 次/秒（每款 8.89），单帧 zebra 43.4ms / TT100K 63.1ms，paint 2.29ms。
- 6 路时期（同一位流扩展，camview 六路地址）：3×2 + 两款轮换，显示 **19–21 fps**、`have=111100`（C1–C4 有帧，C5/C6 无数据，`err=0`）、每路采集 21–23 fps，整体推理 **15.4–16.5 fps**、每款 7.7–8.2 fps，单帧 44/63ms，paint 17ms（`rga=1`）。
- 单路 C1 + 两款轮换：采集 **28–29 fps**、显示 **22–24 fps**、paint **13.9ms**、整体推理 **16.5 fps**。推理线程探针（`DET_BENCH` 下的 `[infer-diag]`）：平均运行 53ms + 平均等帧 7ms；按单次均值 52ms 推算的轮换上界约 19.2/s，剩余差距来自每轮约 7ms 的管线开销。
- 位流与驱动必须匹配：当前 64K-BAR0 的位流会让 `pango_pci_driver` probe 失败（`-EINVAL`）且 ioctl 触发内核 Oops；实例被强杀后驱动会残留 TX buffer（dmesg `TX Buffer already allocated!`），需 `rmmod/insmod` 或重启才能再起。正式 `/root/npu/detview/detview` 未替换。
