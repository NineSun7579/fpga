# RK3568 独立四方位环视工具

版本日期：2026-10-07。该工具独立于detview，不调用NPU；实际板端程序和未标定配置已实测。

C1/C2为同向前双目，C3左，C4右，C5/C6为同向后双目。四个方位分别投影：前、后双目每组使用一眼，另一眼作新帧备用。C5当前为静态输入时，后方自动选用C6。没有真实双目外参，不生成双目深度、不同时叠加两眼、不扩大双目视野。

## 两种HUD

- `1`或`Tab`：GPU 480p环绕视图，鼠标水平/垂直拖动转向，滚轮调整视场角。直接投影四路纹理，并对方位重叠区做羽化；图像先在640×480 GPU帧缓冲投影，再放大显示。
- `2`：360俯视图，四个地面四点单应逆映射在后台OpenCV合成，并绘制车辆轮廓/前方箭头。

两种模式均保留未标定提示。默认方向与地面四点只供预览，不代表可测距、无接缝或真实车辆尺度。当前C1/C2/C3/C4/C6均有实际新帧，C5输入停止；测试中C6承担后向画面。

## 标定

请按[CALIBRATION_GUIDE.md](docs/CALIBRATION_GUIDE.md)操作。指南覆盖棋盘格采集、针孔/鱼眼K/D计算、配置导入、方向修正、地面四点、独立点验收与常见故障；本次开发未替用户填写标定参数，所有`intrinsicCalibrated`/`yawCalibrated`/`groundCalibrated`保持false。

[tools/calibrate_intrinsics.py](tools/calibrate_intrinsics.py)可由用户在电脑上计算单眼K/D，它不会修改板端配置。已保留旧错误布局配置备份；不得从备份恢复到当前工具。

## 运行

先正常退出detview/camview，因为现有PCIe驱动由一个应用独占：

```sh
sudo -E bash /userdata/surround360/run_surround360.sh
sudo -E bash /userdata/surround360/restore_detview.sh
```

程序：`/userdata/surround360/surround360`。配置：`/userdata/surround360/calibration.json`。截图：`/userdata/surround360/screenshots/`。板端命令与本地源码一致。

## 实测与限制

3568最终实测显示约20FPS环绕、14–16FPS俯视短测；输入采集C1/C2/C3/C4/C6约24–29FPS且零读取错误，C5仅静态帧。拖动、HUD模式切换、标定面板、截图均通过。短测包含切换和截图，不是持续性能认证。

驱动复查：PCIe端点5GT/s×2、MSI/BUS MASTER已启用，重新加载原驱动和PCIe重扫后DMA中断持续增加，验证窗口无新错误。未改驱动源码或FPGA。早期MSI/DMA超时的根本原因和永久修复条件未证明，应继续观察；不能把一次恢复记录为全链路长期可靠。

## 来源与实现

独立C++17、Qt5、OpenGL ES2与OpenCV4实现：针孔/鱼眼视角投影、四方位/双目单眼选择、几何有效区羽化、受限曝光匹配、帧龄渐退、缓存地面单应映射和原子JSON配置。算法参考与许可证见[OPEN_SOURCE_REFERENCES.md](docs/OPEN_SOURCE_REFERENCES.md)；未复制外部车辆资产、Jetson CUDA代码或其他车辆标定数据。

八组引擎自检、采集合成自检、Mali/GLES着色器与实际交互检查均已通过。真实摄像头和未标定预览证据在[RESULT.md](RESULT.md)及`evidence/`。已知限制：C5静态，镜头/地面未标定，近物视差与双目同步未解决。
