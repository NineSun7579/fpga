# 四路 detview 与道路分割

本目录基于板端 `/root/npu/detview/main.cpp` 的 YOLO 检测界面，加入四路 OV5640 采集。四路 DDR ping/pong 地址与板端已运行的四路 `camview` 一致：C1 `0x00800000/0x00A00000`、C2 `0x00C00000/0x00E00000`、C3 `0x01000000/0x01200000`、C4 `0x01400000/0x01600000`。每路用 `base + 640×480×2` 的帧标签判断新帧，共用现有 Pango PCIe DMA 驱动；不新增内核 ioctl。

相机选项为 C1–C4 与 Quad。单路模式对该路画面推理；Quad 显示 2×2 四路画面，对 C1 推理并在 C1 区域叠加结果。保留原有 YOLO 模型切换和 DFL 解码；`/root/npu/lane_linknet/` 中的 LinkNet 二分类/九分类模型走逐像素分割路径，并以半透明颜色覆盖选中相机。

在 RK3568 上使用 Qt5、RGA 和 RKNN runtime 构建：`qmake detview.pro && make -j2`。可用 `QT_QPA_PLATFORM=offscreen ./detview --lane-selftest`、`--dfl-selftest` 验证解码。`--model zebra-merged-v3-rm8` 或 `--model lane640-binary` 按路径子串选择模型。

板端隔离编译通过，两项自检通过；实测 Quad 四路显示约 15–18 fps，C1 YOLO 推理约 25–27 fps，两种 LinkNet 模型均成功初始化。当前画面为室内，不能据此判断路面标线识别精度。旧版源码和二进制备份在 `/root/npu/detview/backup_pre_quad_20260927/`。
