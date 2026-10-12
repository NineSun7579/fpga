# C3/C4 单幅 640×480 双路 YOLO 上板验证报告

日期：2026-10-10。隔离程序 detview_cam34_composite，源码位于 candidate_cam34_composite_viewer。

## 实施范围

本版在 RK3568 接收两路 RAW 后执行压缩拼接。C3/C4 各从 640×480 横向均值压缩为 320×480，左 C3、右 C4，得到一个 RGB888 640×480 输入；一个 RKNN 调用包含两路图像。完整视野和全部 480 行保留，物体横向宽度缩为原来的一半。

FPGA RTL、比特流和相机 DDR 地址未修改。PCIe 仍传输两张 RAW，不能声称传输带宽减半。测试期间仅采集 C3/C4，F 可切回六路，Q 正常退出。旧安装程序未替换。

## 模型与验证

实际测试模型 /root/npu/mvp/MVP_accuracy_round1_rk3568_int8.rknn，查询输入形状 [1,480,640,3]。actual_rknn_input.png 保存实际送入 RKNN 前的 640×480 RGB 图像。框输出内部 canonical y+80 在显示/原相机坐标映射时移除，原相机 x 坐标按 2 倍恢复。跨拼接边界框标记 crosses_seam，按中心归属，不把一个跨界预测伪造为两次检测。

RAW 快照独立解码并逐相邻列取均值，与合成图比较 921,600 RGB 字节，差异 0。两路 RAW 图像内容不同。cam34、矩形几何/trafficlight、camera DMA、frame metrics、MVP round1 五组自检全部通过。测试仅证明输入、推理和映射链路；没有标注数据集，不能据此宣称准确率提升。桌面场景中也有 vehicle 误检。

## 实测帧率

运行 100 秒，前两个约 5 秒窗口剔除；显示有效计数区间 86.101 秒。

| 指标 | 结果 |
|---|---:|
| C3 新帧采集 | 26.02 fps |
| C4 新帧采集 | 26.06 fps |
| C3 新画面上传 | 25.33 fps，2181 帧 |
| C4 新画面上传 | 25.28 fps，2177 帧 |
| 双路都更新的合成帧 | 25.51 fps，2160 对 / 84.684 秒 |
| YOLO 完成结果持续计数 | 17.50 次/秒，1482 个 / 84.684 秒；窗口读数范围 16–19 |
| 单次推理耗时 | 46.38 ms（运行输出均值） |
| 任一路更新触发的区域新绘制 | 32.12 fps，不等于两路都更新帧率 |
| 推理失败 | 0 |
| DMA 失败 | 0，六路 error 计数均为 0 |

完成率来自 GUI 实际收到的完整推理结果，在两个 host monotonic 配对标记之间计数（边界约 ±1 个结果）。5 秒周期抽样的短窗口平均为 17.29 fps，持续计数为 17.50 fps。每次完成包含两路，不能把两路 17.5 次识别称作 NPU 35 次推理。采集配对使用 DMA 返回时间，要求年龄 ≤100 ms、偏差 ≤40 ms、相同 source generation 且两路序号都推进；不是曝光同步证明。

## 板端恢复和运行

实施开始时设备已有 ENODEV：无进程占用、PCIe 已绑定、驱动 refcnt=1。首次黑屏冒烟失败已保存为 failed_device_smoke.log。重启 RK3568 后，重新加载重启前同一份 /userdata/linaro/fpga-zero-copy-driver-stage/pango_zc.ko（srcversion=4B81EAFBCEECC53AA2EBFAA），绑定 3c0800000.pcie 并等待异步枚举后，设备打开成功。没有重新烧写 FPGA 或 SPI Flash。

100 秒测试正常退出，确认无设备占用、驱动 refcnt=0 后，再启动同一已验证程序持续运行。运行脚本：

```sh
sudo /userdata/linaro/ov56401-cam34-shared-20261010/run_cam34.sh
```

程序已运行时先按 Q 退出；启动脚本拒绝与已有设备 owner 冲突。

可执行文件：/userdata/linaro/ov56401-rgb888-viewer_build_1791627094983637700/detview_cam34_composite

SHA256：18a9a1c71ec0d940f5004e8b76e675b8195f0f5f63d82e9c7a42a2d2bed13189

## 证据文件

- verified_rk3568_desktop.png：RK3568 X11 桌面实拍截图，包含 C3/C4 标签和模型框；不是生成的示意图。
- cam34_input_640x480.png：第一对 RAW 的合成结果。
- actual_rknn_input.png：推理线程实际 RGB 输入。
- cam3_raw_640x480.png / cam4_raw_640x480.png：上述合成的原始两路快照。
- measured_runtime.log：100 秒实测完整日志。
- fps_summary.json / inference_counted_fps.json / pixel_verification.json：统计、持续推理计数及字节比对结果。
- ../cam34_full_selftests.log：五组最终自检。
- measured_launch.json：测试启动参数及可执行身份。
