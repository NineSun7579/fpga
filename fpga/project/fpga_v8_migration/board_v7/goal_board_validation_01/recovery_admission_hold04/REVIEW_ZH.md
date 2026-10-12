# 实际 viewer 身份不符，未执行暂停

hold_viewer.py要求boot、精确PID/argv/exe/ELF hash及BME=0均符合预期才允许SIGSTOP。实际在argv检查处失败，尚未执行os.kill或配置/sysfs/DMA操作。action.receipt.json及原始stderr保留失败。

后续只读实测PID14889的exe为/userdata/detview-hdmifull/detview-hdmifull，argv为--model MVP_rk3568_int8 --video /userdata/linaro/detview-video-work/media/VID_20260912_151339_480p30.mp4 --video-loop --fullscreen --no-tracking。这与此前预期driving-demo不同；未暂停本地视频进程，未将它当作真实相机/FPGA运行证据。

recovery_state_refresh03实测boot未变、端点Command0402/BME=0、父桥Bridge Control0000/SBR=0、设备fd owners为空、固定驱动hash/build-id一致。这些只说明采集时状态，不证明全域DMA drained或持续admission停止。仍需具体恢复动作、完整SRAM重载与真实reboot会话边界。

本次admission hold未成功，不得写accepted、已暂停或已恢复。原程序保留用于审计，重试必须新目录和当前身份依据。
