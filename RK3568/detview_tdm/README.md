# detview YOLO 时分复用

本目录基于四路 `detview` 增加 2–4 款 YOLO 检测模型轮换。一个推理线程顺序使用各模型的 RKNN 上下文，每个模型只加载一次；相机或视频解码继续提供最新帧，推理忙时覆盖待处理帧，避免积压和重播旧画面。内核 PCIe 驱动与四路 DMA 地址协议不变。

## 使用

界面点击“选择轮换模型”，勾选 2–4 款 YOLO 检测模型，再按“轮换”；点击取消后回到当前单模型。命令行可传逗号分隔的唯一文件名子串。子串必须各自只匹配一款已扫描模型，避免误选：

```sh
./detview --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --fullscreen --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --video demo.mp4 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --video /dev/video0 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
# 定时结束，用于短时测试：追加 --duration 30
```

`--video` 也接受网络 URL，由 `ffmpeg` 解码为 640×480 RGB，再 letterbox 到 640×640。视频模式不访问 PCIe；不带 `--video` 时沿用四路 FPGA/PCIe 采集。Quad 显示四路并对 C1 推理，选择 C1–C4 单路时对该路推理。切换相机时清除旧结果。

## 采集与显示

四路采集与显示采用运行版 `camview` 的结构：每路一个采集线程按帧标签轮询并 DMA 读整帧（共用一条 DMA 通道，读写串行化），采集线程按“代（gen）变化 + 默认 33ms 节流”合成 2×2 RGB565 画面并投递到 GPU；显示用 `QOpenGLWidget`（Mali EGL/ES2）直接上传纹理、由 GL 做 letterbox 缩放，检测框与车道掩码在 CPU 侧画进覆盖图后整块 blit（直接在 GL 窗口上画文字会被 ES2 的字形图集画花）。推理输入只转换 C1 这一路为 640×640，不再逐帧做四路 RGB565→RGB888 与 QPainter 拼图缩放。

环境变量：`DETVIEW_MIN_MS` 覆盖显示节流（默认 33ms，0 = 不限速）。调大可在推理与显示之间更偏向推理。`DETVIEW_GEO=1` 每秒打印一行窗口几何（`win= / dpr= / screen=`），用于排查缩放或全屏尺寸不一致。

启动参数 `--fullscreen` 直接全屏（等价于运行后按 `F`）。板端 XFCE 的“窗口缩放”会把 Qt 逻辑尺寸和 X 实际窗口拉开（例如 1.25x 时 Qt 认为 1920×1080 的窗口只有 1536×864），全屏时 GL 画面只能铺满左上角，因此程序启动时固定 `QT_SCALE_FACTOR=1` 并关闭自动屏幕缩放；如确需缩放可用同名环境变量覆盖。

每款模型保留最近一次检测框，框标签带模型名；超过 2 秒未更新的结果自动隐藏。轮换时工具栏显示“轮换 N 款 | 本次 X ms | 推理 Y fps | 总检测 Z”，其中推理帧率是任意模型完成一次推理的整体速率（指数平滑，与各模型单独更新频率不同）。状态栏显示各模型耗时、有效检测数量、每模型更新频率和结果年龄。切换相机或手动选单模型会清除旧结果。LinkNet 分割模型仍走原来的单模型路径，不参与 YOLO 轮换。多个模型共用一颗 NPU，单模型更新频率会随所选模型数下降。

## 验证

```sh
qmake detview.pro && make -j2
QT_QPA_PLATFORM=offscreen ./detview --dfl-selftest
QT_QPA_PLATFORM=offscreen ./detview --lane-selftest
QT_QPA_PLATFORM=offscreen ./detview --rotate-selftest image.ppm zebra-merged-v3-rm8,tt100k-anneal-c12
```

板端自检：`DFL_SELFTEST_PASS`、`LANE_SELFTEST_PASS`；静态图轮换自检两款各 40 次、四款各 20 次严格轮转，未重新初始化上下文。

2026-09-29 四路实时实测（PCIe BAR0 8K/BAR1 4K/BAR2 4K，驱动已绑定，隔离构建 `/userdata/linaro/detview-tdm-build-20260928`）：Quad + 两款轮换跑 70s，`have=1111`、`err=0/0/0/0`，四路显示 **23.13 fps**（每路采集约 23 fps），轮换吞吐 **17.77 次/秒**（每款 8.89），单帧 zebra rm8 43.4ms、TT100K 63.1ms，paint 平均 2.29ms。同机位 camview 为 22.0 fps、每路 24.8–34.1 fps。相比改造前的单线程 CPU 拼图路径，显示帧率 15.08 → 23.13 fps，轮换吞吐 14.89 → 17.77 次/秒；代价是显示管线吃满 DDR/CPU 后单帧推理慢约 9–12%，可用 `DETVIEW_MIN_MS` 调节。正式 `/root/npu/detview/detview` 未替换。

1920×1080 全屏实测：`--fullscreen` 下窗口 1920×1080、`dpr=1.00`、GL 组件 1898×1006，画面铺满无桌面透出，显示约 21 fps（面积大于窗口模式，略低于 23 fps）。
