# RK3568 GPU 驱动检查

结论：Mali-G52 的内核驱动和 EGL/OpenGL ES 硬件路径可用；桌面 GLX 路径退回 CPU 软件渲染，并存在 Xorg 显示翻页超时。不能据此认定 GPU 硬件或整个驱动失效。

## 实测证据

- 系统 Debian 12，内核 6.1.99；Mali 内核 DDK g25p0，用户态 libmali g24p0。版本不同，但本次 EGL 上下文创建、绘制和读回成功，未证实 ABI 不兼容。
- /dev/mali0 存在，fde60000.gpu 绑定 mali 驱动；Probed as mali0。当前启动日志未见 GPU job fault、hang 或 reset。
- root 和 linaro 两种身份均通过 EGL 1.5 / GLES smoke test：vendor ARM，renderer Mali-G52，OpenGL ES 3.2，清屏后的像素读回 [255,0,0,255]，GL error=0。
- 当前 camview 位于 /root/ov5640/camview_display_optimized，加载 libmali.so、libmali-hook.so 和 mali/libEGL.so，并打开 /dev/mali0。检查期间 GPU utilisation 单点约46–51%，频率800MHz；这些不是持续性能基准。
- Xorg 启动日志明确 glamor X acceleration enabled on Mali-G52，glamor initialized。
- glxinfo -B 显示 llvmpipe、Accelerated:no；stderr 报 failed to create dri3/dri2 screen 和 failed to load driver: rockchip。Xorg 启动日志有 AIGLX driver entry point failed，随后 GLX 使用 DRISWRAST。
- /var/log/Xorg.0.log 在一次取样时累计218条 crtc-72 flip timeout，后续检查仍有新增。可能影响显示流畅度，具体原因尚未隔离；不等同于 GPU shader 崩溃。
- 现有 20-modesetting.conf 配置 AccelMethod glamor、FlipFB always。DRI选项被Xorg报告未使用。翻页超时与配置/显示提交路径的关系需独立实验确认。
- 内核启动时报缺少 mali-simple-power-model 设备树参数，随后使用已配置 mali-g52_r1-power-model 和 fallback；这些警告没有阻止 GPU 初始化。

## 后续方向

优先排查 Xorg modesetting/FlipFB 的翻页路径和应用提交方式；对依赖桌面 OpenGL/GLX 的程序另行核对 Mesa/厂商库集成。当前相机程序走 Mali EGL 路径，不能以 glxinfo 的 llvmpipe 输出推断相机软件渲染。此次未修改驱动、Xorg配置或重启显示服务，也未停止相机程序。检查期间 camview PID 自行变化，因此最终通过动态 pgrep 获取当前进程映射。

原始记录：rk3568_gpu_initial.json、rk3568_gpu_display.json、rk3568_gpu_egl.json、rk3568_gpu_final_checks.json。可复用测试：project/tools/probe_rk_gpu_egl.py。
