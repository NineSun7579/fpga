# FPGA C3/C4 压缩直传、200%六路显示验证报告

日期：2026-10-10。

FPGA在DDR写入前把C3/C4从640×480做2×2 RGB565均值降采样至320×240。RK3568只读取每路153600字节图像和16字节帧标签，不再传输两路全尺寸RAW。C1/C2/C5/C6继续原路径。

六路3×2网格、窗口大小、位置、4:3比例保持。C3/C4的320×240纹理在原逻辑640×480窗格内由GPU宽高各放大2倍；全窗口适配屏幕统一作用于所有窗格。两路压缩图像左右拼成640×240，上下各120行灰114，成为MVP-R1的640×480输入。共享框去掉canonical80+内容120偏移、x/y均乘2，映射回各自窗格。

| 路 | 实际PCIe图像尺寸 | 图像载荷/帧 | 新帧采集 | 新画面显示 |
|---|---|---:|---:|---:|
| C1 | 640×480 | 614,400 B | 44.86 fps | 28.52 fps |
| C2 | 640×480 | 614,400 B | 44.87 fps | 28.75 fps |
| C3 | 320×240 | 153,600 B | 25.73 fps | 22.80 fps |
| C4 | 320×240 | 153,600 B | 25.73 fps | 22.68 fps |
| C5 | 640×480 | 614,400 B | 40.37 fps | 28.08 fps |
| C6 | 640×480 | 614,400 B | 40.34 fps | 27.91 fps |

共享新输入：25.71 fps。
完整YOLO结果：1726个/107.363秒=16.08次/秒，每次同时覆盖两路。
单次推理平均：42.03 ms。
采集列采用[ capture ]每个窗口完成帧数/时长的delivered_fps均值；HUD滚动整数采集读数另存fps_summary.json。
显示有效计数：106.108秒，已剔除启动阶段。
DMA故障和推理失败：未发现DMA故障，推理失败0。

cam3_dma_identity.json及cam4_dma_identity.json记录实际DMA为153616字节。C3/C4帧标签在DDR基址+153600；readonly geometry magic、尺寸、帧长和stride在启动时核对。等待两组bank完整发布后才读新tag位置。主机长度guard禁止C3/C4超过153616字节的读取，无CPU再次降采样、无RAW回退。

相同帧数下，C3/C4图像载荷合计从1228800降到307200字节，减少75%；完整六路各传一帧从3686400降到2764800，减少25%。比例不包含轮询、tag和PCIe封装，不能等同于未测得的整体速度提升。

板端两张压缩图像与实际模型输入独立组合比对：921,600RGB字节差异0。2×2滤波、DDR打包、tag提交由完整RTL golden、真实Pango FIFO、AXI背压、短帧恢复和tag B响应延迟测试验证。板端未传RAW，因此不宣称板端同帧RAW滤波比对。模型有场景误检，此项不是准确率评估。

时序总结与详细报告均通过后才生成并烧录SRAM，SPI Flash及旧安装程序保留。
Bitstream SHA256：4e0e189d2bde28de33ef259fb4465147296fdacd65680222a7231fb128a516ba。
Viewer：/userdata/linaro/ov56401-cam34-wire-viewer-build-1791637623370314600/detview_cam34_fpga_compressed。
Viewer SHA256：ebaa6be49905c690726d349ad0e07055e223a6c19dbcf28d27203f2fddb879e2。

证据：verified_six_camera_desktop.png、cam3_wire_320x240.png、cam4_wire_320x240.png、actual_rknn_input.png、cam3_dma_identity.json、cam4_dma_identity.json、runtime.log、fps_summary.json、inference_counted_fps.json、pixel_verification.json。


现场为夜间低照度，六个摄像头画面都较暗，C3本轮没有检测框。因此截图证明真实六路布局、原窗口200%显示和实时刷新；传输身份与输入像素校验通过。本轮未验证亮场目标识别准确率，不将右侧显示器上的模型误检作为正确识别证明。

120秒试验正常退出后已确认无device owner且驱动refcnt=0。相同已验证比特流与viewer随后重新启动持续显示，PID记录在live_launch.json。板端启动脚本：/userdata/linaro/ov56401-cam34-wire-trial/run_cam34_wire.sh。按Q正常退出，F切换共享识别，六路显示/压缩纹理不变；不会切回RAW传输。SRAM版本断电后会回到原SPI程序，新的host会拒绝旧几何而非悄悄传RAW。
