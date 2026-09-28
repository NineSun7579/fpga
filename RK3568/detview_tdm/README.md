# detview YOLO 时分复用

本目录基于四路 `detview` 增加 2–4 款 YOLO 检测模型轮换。一个推理线程顺序使用各模型的 RKNN 上下文，每个模型只加载一次；相机或视频解码继续提供最新帧，推理忙时覆盖待处理帧，避免积压和重播旧画面。内核 PCIe 驱动与四路 DMA 地址协议不变。

## 使用

界面点击“选择轮换模型”，勾选 2–4 款 YOLO 检测模型，再按“轮换”；点击取消后回到当前单模型。命令行可传逗号分隔的唯一文件名子串。子串必须各自只匹配一款已扫描模型，避免误选：

```sh
./detview --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --video demo.mp4 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
./detview --video /dev/video0 --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
# 定时结束，用于短时测试：追加 --duration 30
```

`--video` 也接受网络 URL，由 `ffmpeg` 解码为 640×480 RGB，再 letterbox 到 640×640。视频模式不访问 PCIe；不带 `--video` 时沿用四路 FPGA/PCIe 采集。Quad 显示四路并对 C1 推理，选择 C1–C4 单路时对该路推理。切换相机时清除旧结果。

每款模型保留最近一次检测框，框标签带模型名；超过 2 秒未更新的结果自动隐藏。状态栏显示各模型耗时、有效检测数量、每模型更新频率和结果年龄。切换相机或手动选单模型会清除旧结果。LinkNet 分割模型仍走原来的单模型路径，不参与 YOLO 轮换。多个模型共用一颗 NPU，单模型更新频率会随所选模型数下降。

## 验证

```sh
qmake detview.pro && make -j2
QT_QPA_PLATFORM=offscreen ./detview --dfl-selftest
QT_QPA_PLATFORM=offscreen ./detview --lane-selftest
QT_QPA_PLATFORM=offscreen ./detview --rotate-selftest image.ppm zebra-merged-v3-rm8,tt100k-anneal-c12
```

板端静态图轮换自检：两款模型各运行 40 次；四款模型各运行 20 次，严格轮转，均未重新初始化上下文。12 秒、约 30fps 视频输入测试中，两个模型持续交替推理且视频解码保持运行。当前 FPGA 位流仅枚举 64KiB BAR0，PCIe 驱动未绑定；实时四路 DMA 模式须待正确 BAR0/BAR1/BAR2 位流恢复后验证。隔离构建位于 `/userdata/linaro/detview-tdm-build-20260928`，未覆盖板端正式 `detview`。
