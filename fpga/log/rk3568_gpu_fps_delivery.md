# RK3568 帧率口径与显示同步验证

当前查看器已运行 CAMVIEW_SWAP_INTERVAL=0，桌面合成保留。帧率文字分为 cap（采集）、up（每路新图像上传）、Swap（Qt frameSwapped 对应的窗口换帧完成通知）。HDMI仍为1920x1080p60；Swap不是物理屏幕扫描出的独立新画面数。

## 计数核对

原HUD每5秒统计实际glTexImage2D/glTexSubImage2D成功调用后的计数，并不是每次60fps采集投递都加1。先前swap计时与20fps上传计数一致，本次独立frameSwapped计数与总上传事件也一致，没有发现统一低报或隐藏的60fps相机更新。肉眼观感无法作为精确帧率测量；60Hz屏幕可以重复扫描较低帧率的相机图像，5秒均值也不会即时反映短时变化。

同一窗口的不同相机并非每次换帧都变化，总窗口FPS不能替代每路up计数。

| 指标 | 23个稳态5秒窗口的均值 | 范围 |
|---|---:|---:|
| 总上传/窗口Swap | 38.78fps | 37.41–39.47fps |
| CAM1新图像上传 | 32.99fps | 31.37–34.80fps |
| CAM2新图像上传 | 32.89fps | 31.12–34.71fps |
| CAM3新图像上传 | 25.41fps | 24.92–25.91fps |
| CAM4新图像上传 | 25.24fps | 24.64–25.82fps |
| CAM5新图像上传 | 31.79fps | 29.30–34.88fps |
| CAM6新图像上传 | 31.34fps | 28.45–34.68fps |

与原默认配置约20fps相比，应用侧取消额外swap同步显著提高窗口更新。采集保持CAM1/2约45fps、CAM3/4约25.7fps、CAM5/6约40.4fps，unstable=0。高速通道尚未全部上传到采集帧率，后续瓶颈仍在呈现吞吐与最新帧合并。

## 验证及当前状态

- 两次C++构建成功，无编译警告。第一次HUD加入连续变化的采集值导致频繁全屏HUD纹理重建，已改为与现有5秒计数窗口一起更新，稳态HUD耗时恢复约0.44–0.49ms。
- 稳态观察83549.11→83663.53秒（114.42秒），flip timeout计数253→253。暂停/恢复之后计数256，不宣称整个操作过程零超时。
- 暂停12秒后六路up均归零、总Upload为0，Swap为0.182fps（一次状态重绘）；随后finally恢复播放。这说明重复显示/状态重绘未冒充新相机帧。
- 实际X11屏幕截图已读取：六路完整、cap/up/Swap标签可读、未见明显行错位。静态截图不能证明物理扫描没有撕裂。
- 最终仅PID27926持有DMA设备，CAMVIEW_TEXTURE_RING=1、CAMVIEW_SWAP_INTERVAL=0，无计时LD_PRELOAD。已恢复播放并核对远端main.cpp与本地字节一致，SHA256 966f2b5558664acdb4eceac96c4cfb56b39332c9951bc405f77a38888fadd43c。
- 正式开机启动脚本未修改；本次保留改善后的运行实例。重启候选可运行 project/tools/start_camview_display.py 1 --swap-interval=0；默认不传参数仍为swap interval=1。
- 远端原版源码和二进制备份：/root/ov5640/camview_display_optimized/main.cpp.before_gpu_fps、camview.before_gpu_fps；本地原版快照log/rk3568_gpu_viewer_main.cpp。

证据：rk3568_gpu_fps_cached_full.txt、rk3568_gpu_fps_verified.json、rk3568_gpu_fps_final_state.txt、rk3568_gpu_fps_screen.png；暂停证据camview_fps_audit_20261003/fpsfix_pause.txt。
