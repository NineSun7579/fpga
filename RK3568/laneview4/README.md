# 四路画面与道路标线分割

`laneview` 以板端已运行的四路 `camview` 源码为基座：继续使用四个摄像头的 DDR ping/pong 帧标签与现有 `/dev/pango_pci_driver` DMA 接口，画面仍由 Mali OpenGL ES 渲染。另起一个推理线程，只保留最新一帧，避免 LinkNet 推理阻塞采集。

## 模型与显示

从 WebDAV `yolo_project/lane_linknet/` 取得并校验以下 RK3568 INT8 模型，部署到 `/root/npu/lane_linknet/`：

- `seg-linknet-lane640-binary-rk3568-int8.rknn`：背景/标线，默认加载。
- `seg-linknet-lane640-multiclass-rk3568-int8.rknn`：背景及 lane0–lane7，使用 `--multiclass` 加载。

输入为从选定相机取得的 640×480 RGB565 帧，转换成 RGB888，并在上下各加 80 像素的灰色填充形成 640×640。模型输出按通道取 `argmax`，去掉填充区后将半透明类别图叠加到对应画面。按 `1`–`4` 选择做标线推理的摄像头。没有路面标线的场景可能看不到彩色叠加。

## 构建与运行

在 RK3568 上安装 Qt5、RKNN runtime 及对应开发头文件，然后运行：

```sh
qmake laneview.pro && make -j2
DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 ./laneview
# 九分类：./laneview --multiclass
```

运行前确认 FPGA 的 PCIe 设备 `0755:0755` 已枚举为 BAR0 8 KiB、BAR1 4 KiB、BAR2 4 KiB，且现有 Pango 驱动已绑定。四路地址与同步逻辑来自正在运行的 `camview`，不需要新的内核 ioctl。首次上板测试中，二分类和九分类 RKNN 均成功初始化，四路画面保持更新；二分类时界面约 20–25 fps，模型推理约 199 ms/帧。室内画面不能验证道路标线精度，需用真实道路场景实测。
