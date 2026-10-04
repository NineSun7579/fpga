# 监看与设置分页验证

在原RK3568板卡、Qt5.15.8、Mali-G52与1920×1080 X11会话验证；源码及可执行文件仍使用`/userdata/linaro/detview-vision-work/`隔离目录。

## 界面改动

- 监看页：独立顶栏/底栏，六路编号及采集/新画面率，各路图像等比布局，选中识别路青色边框。模型列表、完整参数与诊断不再覆盖相机图像；检测框仍在对应相机图像上显示。
- 设置页：左右分栏，六项可选设置与识别策略、实时性能、模型列表、设备状态分别布局；Tab来回切换，设置页Esc返回，G回六路总览。
- 设置键：↑/↓选项，←/→调整，Enter切换。暂停时改相机立即更新冻结画面布局；长按Esc的重复事件不会继续触发退出。轮换模式显示“按各模型配置”，避免设置显示与实际推理坐标格式不一致。
- 设置页继续采集和识别，相机新画面率不累计；返回监看上传最新内容。切换页面不等同于暂停。

## 构建和截图检查

最终板端`make -j2`成功、无编译warning，`--vision-selftest`通过，包含tracker、DMA、208项帧率检查及vision自测。日志见[UI验证目录](../logs/tdm_ui_validation/)。

首版设置页在Mali上直接绘制字形出现花屏。改用CPU绘制缓存页面位图、GPU显示位图后，最终[设置页截图](../logs/tdm_ui_validation/settings.png)中文字正常，栏目和快捷键完整。与监看页相同，不再使用Mali的直接字形绘制路径。

[监看截图](../logs/tdm_ui_validation/monitor.png)显示六路与独立工具栏；[阈值截图](../logs/tdm_ui_validation/settings_threshold.png)显示25%调到30%，随后恢复25%；[暂停截图](../logs/tdm_ui_validation/settings_paused.png)显示暂停状态。暂停后在设置中从六路切到C2，[C2冻结画面截图](../logs/tdm_ui_validation/paused_camera_2.png)的顶栏、相机编号、冻结图像一致，采集/新画面为0。

第二轮自动验收在上述检查后处于停止状态，detview成为僵尸进程，板上另一个camview已运行；原始日志保存为`interrupted_ui-run.log`和`interrupted_detview.log`。用户随后确认反复切回camview是另一个agent在操作，不应归因为应用自行重启或UI故障。未将该中断轮声称为完整通过。清理本轮停止的测试进程后重新执行完整键盘检查；脚本跳过已经退出但尚未回收的僵尸进程，不重复向其发送按键。

最终完整脚本退出0，日志记录`UI_ACCEPTANCE_FINISHED 24104`。Tab进入设置、阈值调整与恢复、Enter暂停与继续、暂停时切C2、Esc返回、V单路、设置页G回六路、Tab后Esc返回均完成；[返回六路截图](../logs/tdm_ui_validation/monitor_grid.png)显示六格、独立顶底栏、正常检测框和约16fps新画面。验收结束时为PID24104，六路总览、默认追踪、阈值25%；05:13:43 UTC额外检查时该进程已结束，camview PID24424再次运行。用户确认另一个agent正在切换程序后，本轮停止操作运行进程，未再启动新版。最后观察状态见`final_state.log`，长时间稳定性未在本轮UI验收中测试。源码SHA256：`0b97248a94d297f2e07d923c4658843440da83c9c2e9acba0d8ffe5e1a20ed96`。

执行脚本：[validate_detview_ui.py](../scripts/validate_detview_ui.py)。屏幕截图使用板上既有qshot，不在detview GUI线程同步保存PNG。只在现有查看程序正常退出、设备无占用后启动新程序，没有改动驱动或FPGA寄存器。

实际界面验收覆盖1920×1080；设置按1280×720逻辑布局整体缩放，较小窗口尚未单独验收。此前的设备独占/断流风险仍见[实板运行记录](LIVE_VALIDATION.md)，本轮UI改动没有解决内核驱动生命周期问题。
