# RK3568 detview：MVP-R1 与识别框防闪烁发布

这是2026-10-07板端已安装并实测的版本。检测框连续三次有效推理观察才显示；无跟踪视频模式漏检缓冲180ms，实际漏检并超过缓冲后重新出现须重新确认。跟踪预测和重复刷新不增加确认次数，来源或模型切换清空状态。

源码目录：[RK3568/detview_tdm](../../detview_tdm/README.md)，根目录detview_tdm兼容副本同步。新增MVP-R1五类640×480INT8检测及绑定模型哈希的类别阈值；保留旧检测、红绿灯和共享/独立车道支持。

## 文件与构建

- `bin/detview-hdmifull`：实际板端程序，SHA256 `3d315e77913fb651b884b817480284d1ad17ad5e794866f4db5c7c50db69cf0b`，需要RK3568板上的Qt5/OpenCV/RKNN/RGA运行库。
- [MVP-R1模型及配置](../../models/detview/mvp_accuracy_round1/README.md)：模型SHA256 `6cdfe6c8d834e2b99994633b483e048819a79c440562a2ea1ccbc55947be03e2`。
- [实测报告](performance/REPORT.md)、日志/CSV、自检、截图与`FILE_MANIFEST.json`：可核对实际版本与测量口径。

```sh
cd RK3568/detview_tdm
qmake detview.pro
nice -n 10 make -j1
QT_QPA_PLATFORM=offscreen ./detview --temporal-selftest
QT_QPA_PLATFORM=offscreen ./detview --mvp-round1-selftest
QT_QPA_PLATFORM=offscreen ./detview --vision-selftest
```

2GB板端用单路编译；此前四路编译后SSH曾失去响应，用户重启恢复，原因未完整诊断。全部八组板端自检以及118项最终时序行为检查通过。默认开启显示过滤；`--no-temporal-filter`可用于对照。

## 部署和回退

板端已有其他查看器时，先正常关闭该查看器，再安装文件。`install_files.sh`只部署文件，不启动查看器、不改驱动/FPGA；已有文件先备份到/userdata/model_imports/下独立目录。

```sh
sudo bash RK3568/releases/detview_temporal_20261007/install_files.sh
export DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0
export QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_egl
sudo -E /userdata/detview-hdmifull/detview-hdmifull \
  --model MVP_accuracy_round1 --video /path/to/road_480p30.mp4 \
  --video-loop --fullscreen --no-tracking
```

常驻预览不带`--shot`，避免GL截图造成停顿。示例道路视频保留在板端，仓库不重复存视频。旧MVP-plus/独立UFLDv2及红绿灯模型仍在各自WebDAV包，文件名/元数据由源码旁README_MVP.md记录；此次模型归档只新增当前MVP-R1，未覆盖旧模型。

回退前正常退出查看器，把安装脚本生成的备份中程序/对应模型文件复制回原路径；备份清单记录原来存在的文件。

## 性能与局限

同640×480道路视频，预热30秒后统计60秒：旧版画面20.07FPS、推理19.22FPS；最终过滤版画面20.52FPS、推理18.63FPS。推理约下降3.04%，最长推理完成间隔106.38ms，无超过250ms的间隔。各条件只测一次，不能把小幅差异解释为统计显著改善或保证任意场景无卡顿；推理间隔不是屏幕逐帧间隔。

ARM多框匹配已优化；300个分散框核心均值160.59→3.55ms，人工全重叠输入168.38→26.50ms。最终视频复测使用修正后的程序；微基准不包含整个Qt显示链路。

新框通常多等待约100ms；只出现一两次的真实目标也会被隐藏，持续误检仍可能显示。本轮没有有标注精度测评。板端重启后PCIe设备节点未出现，本次以视频模式运行实际NPU验证，不据此声称实时HDMI输入通过。
