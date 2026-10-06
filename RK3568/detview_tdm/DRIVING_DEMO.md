# 十字路口智能驾驶模拟

`--driving-demo` 使用 C5+C6 的完整 HDMI 画面，叠加模拟车辆的车道、行驶方向、停车状态及闯红灯报警。程序输出用于视频演示，不连接真实车辆执行器。

## 现有功能演示范围

本版先完成赛题3的十字路口模拟：识别人、车、斑马线和信号灯，按键选择车道或车辆行为，用图像箭头和模拟 LED 状态表示行驶，用红色边框报警。虚实线变道、停止线和导航识别不包含在本版验收范围。

50K 先选择 HDMI（Key2/L15），电脑播放测试视频。查看器的 F 键只切显示与推理布局，不能代替 50K 的输入选择。C5/C6 任一半幅缺失、过期或不同步时，画面提示输入异常，自动及强制模式均暂停模拟行驶；恢复后绿灯重新确认。

## 启动与维护

也可使用现成视频模拟输入，仍由真实模型识别人、车、斑马线与信号灯，不访问 PCIe：

```sh
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh restart \
  --video /userdata/linaro/detview-video-work/media/VID_20260912_151339_480p30.mp4 \
  --video-loop --driving-video-padded480
```

`--driving-video-padded480` 仅用于已知 640×480 视频且有效图像为中间 640×360、上下各60行灰边的素材；其他视频不要添加该参数。视频模式保持16:9显示与检测框映射，画面及日志标明本地视频来源。缺少红灯片段的道路视频只能验证已有类别识别与操作，不能据此宣称实景红灯报警验收通过。

部署后的入口为 `/userdata/detview-driving-demo/run_driving_demo.sh`：

```sh
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh start
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh status
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh restart
sudo -n bash /userdata/detview-driving-demo/run_driving_demo.sh stop
```

入口检查模型、采集设备及已有占用者；保留每次运行日志。异常退出时仅重启本程序，不改 FPGA 位流或重载驱动。不安装开机启动。其他采集程序占用设备时拒绝启动，避免两个程序争用 DMA。

```sh
./detview --driving-demo --fullscreen --no-tracking \
  --rotate-model trafficlight-16cls,wb_v4_combo
```

两个模型轮换识别：16 类信号灯模型判定普通机动车灯、左转灯、直行灯及右转灯的红黄绿；三分类模型识别人、车和斑马线。未显式选模型时，演示模式自动选择这两个模型。HDMI 传输图恢复为 16:9，全图参与识别。

| 按键 | 模拟输入 |
| --- | --- |
| ← | 车辆在左转车道 |
| ↑ | 车辆在直行车道 |
| → | 车辆在右转车道 |
| A | 自动：红灯停车、稳定绿灯行驶 |
| X | 人工停车 |
| B | 强制行驶；适用红灯亮起时报警 |
| F | HDMI / 六路视图切换；退出 HDMI 时演示停车 |
| S | 保存当前真实 GL 画面 |
| Shift+F | 窗口全屏切换 |

所选车道有方向灯时，优先使用相应方向灯；没有相应方向灯时使用普通机动车灯。其他车道的方向灯及掉头灯不授权当前车道行驶。红灯立即停车；黄灯、识别冲突、熄灯、未知或过期信号均不会自动放行。绿灯需要连续确认后才放行，切车道及来源切换会重新确认。人工停车优先于绿灯。

箭头显示所选方向，行驶时亮绿色，停车时显示灰色。画面圆点模拟 LED 输出：LED0 左转、LED1 直行、LED2 右转，只在相应行驶方向点亮；ALARM 点及红色边框表示闯红灯。此版本选择图像叠加输出，未驱动板上物理 LED。

信号来自识别模型的类别，而不是按键指定灯色。按键只改变模拟车辆车道或行为。每次识别结果携带原始采集时间，旧帧不能刷新信号有效期。日志 `[driving]` 记录状态变化，便于对照视频和操作验证。

```sh
QT_QPA_PLATFORM=offscreen ./detview --driving-selftest
QT_QPA_PLATFORM=offscreen ./detview --driving-overlay-selftest /tmp/driving_overlay_tests
```

自测覆盖红灯停车、绿灯放行、强制闯红灯报警、三车道选择、方向灯优先级、冲突及过期信号。实际 HDMI 验证及截图另记录在验收报告中；未观察到的实景条件不以模拟测试代替。

默认车道是直行；可用 `--driving-lane left|straight|right` 指定启动车道。绿灯确认要求至少两次不同采集帧，覆盖至少 200ms；信号有效期为 1200ms，判定置信度门槛为 0.4。行人、车辆、斑马线的计数用于辅助显示；此演示的行驶判定按当前车道信号灯执行。
