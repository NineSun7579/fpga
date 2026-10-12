# RK3568 GPU 与显示同步排查

## 结论

已将当前 camview 约20fps上传瓶颈定位到 EGL/X11 显示提交同步路径。Mali EGL/GLES 绘制与读回正常，当前应用使用硬件驱动；桌面 GLX 的 llvmpipe 回退是另一个问题，不能解释当前应用的全部瓶颈。

应用 swap interval=1、桌面合成开启、Xorg FlipFB=always 时，eglSwapBuffers 平均阻塞约32ms，下一帧 glClear 获取窗口缓冲区约10ms。仅将应用 swap interval 临时设为0，保留桌面合成与FlipFB，上传率达到约39fps，glClear 降到约0.24ms。这证明应用同步设置与当前显示栈的组合产生明显等待；尚未独立证明 FlipFB、合成器或驱动内部队列各自的具体机制。

## 同一候选的实测对比

| 配置 | 稳态上传事件/秒 | EGL swap平均ms | glClear平均ms | 20秒窗口新增flip timeout |
|---|---:|---:|---:|---:|
| 原配置：合成开，swap interval=1 | 20.00 | 31.67–31.92 | 10.11–10.32 | 0 |
| 合成关，swap interval=1 | 25.32–25.53 | 20.19–20.95 | 12.27–12.68 | 0 |
| 合成开，swap interval=0 | 38.67–39.28 | 16.98–18.07 | 0.23–0.25 | 0 |

上传率来自应用成功纹理上传事件，swap数来自调用计时；不是显示器真实扫描出的独立相机帧率。初始5秒包含启动预热，不纳入上述稳态上传范围。所有测试均使用完整六路640x480输入、一纹理槽、NoPartialUpdate，不改FPGA或DMA采集。

六路采集一直正常，恢复后CAM1/2约45fps、CAM3/4约25.8fps、CAM5/6约40.4fps，unstable=0。GPU单点utilisation基线44%、合成关46%、swap0为64%，没有满载证据。

## 翻页超时的解释边界

基线计数230→230，合成关236→236，swap0为245→245。新增报错出现在这些窗口之间、窗口关闭/重新打开或合成状态切换附近；恢复后日志最近三条为83033.880、83037.364、83037.501，恢复检查时间83066.43。较早累计超时不能当作持续渲染时GPU反复卡死的证据。短窗口不足以排除低频稳定态超时，长期观察仍有必要。

当前HDMI输出1920x1080p60，video_port0正常激活，DSI端口未启用。未见GPU job fault/hang/reset。内核g25p0与用户态g24p0版本不同，但现有实测没有证明ABI故障。

## 当前状态与建议

所有实验在finally恢复桌面合成true，并重启原候选：CAMVIEW_TEXTURE_RING=1、默认swap interval=1；未保留LD_PRELOAD。恢复后仅一个camview PID27414持有DMA设备，原20fps行为再次出现，支持配置对比可重复。未修改Xorg配置、驱动包、正式启动脚本或重启桌面。

优先使用应用侧现有CAMVIEW_SWAP_INTERVAL=0做更长时间画质/撕裂/上传率验收，成功后再调整默认启动配置。关闭合成器提升较小，不推荐作为最终处理。GLX问题需要单独核对Mesa/厂商GL接口集成；不能用替换GPU内核驱动的方式推断能解决本次同步等待。

## 证据与工具

- rk3568_gpu_present_baseline.json、rk3568_gpu_present_compositor_off.json、rk3568_gpu_present_swap0.json：完整应用日志、计时与超时计数。
- rk3568_gpu_investigation_restored.txt：恢复后环境与采集状态。
- project/tools/gpu_present_timing.c：只统计eglSwapBuffers、glClear、glTexSubImage2D调用耗时。
- project/tools/measure_gpu_present.py：25秒可回滚对比，先验证计时库EGL读回测试，再停止/重启同一个显示候选。

第一次计时库启动失败，程序在渲染初始化阶段退出；未擦写或修改设备，finally恢复原查看器。原因是EGL通过动态加载而非直接链接，RTLD_NEXT无法得到相应符号。已改为从实际Mali EGL库解析，并在停止查看器前加入EGL绘制读回验证；后续三组计时成功。测试库仅位于/tmp，不参与当前程序。
