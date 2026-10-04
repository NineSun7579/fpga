#!/bin/bash
# detview 自愈守护：应用会自己 exit(3)（连续 DMA 失败，或 60 秒没有新帧——
# 后者覆盖"相机停摆/ioctl 被驱动信号量卡住导致应用挂着不退"的情况），这里负责重启。
# 不需要 rmmod/insmod —— 驱动的 pango_cdev_open 每次打开设备都会把 g_dma_flag
# 等状态清零，所以"退出进程 + 重新打开"就等于恢复。
# 连续失败 3 次时还会做第二阶段恢复：PCIe remove/rescan + 驱动重载——位流复位后
# 不做这一步，总线主控 DMA 会静默死锁（项目文档 ov56401/project/CLAUDE.md）。
# 用法: sudo setsid bash run_detview.sh --fullscreen --rotate-model a,b
exec 9>/tmp/detview.lock
flock -n 9 || exit 0
echo $$ > /tmp/detview_supervisor.pid   # 便于外部用 PID 精确停止（不要用 pkill -f，会误伤调用方）

export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
cd "$(dirname "$0")" || exit 1

fails=0
while true; do
    ./detview "$@"
    rc=$?
    [ "$rc" -eq 0 ] && exit 0
    fails=$((fails + 1))
    echo "[supervisor] detview exited rc=$rc (consecutive=$fails); restart in 3s" >&2

    # 第二阶段恢复：连续失败说明不是单次丢 MSI，而是 FPGA 位流复位/PCIe 侧失步。
    # 项目文档（ov56401/project/CLAUDE.md）明确：位流复位后必须做
    # PERST/remove + rescan + rmmod/insmod，否则一切总线主控 DMA 静默死锁
    # （MMIO 正常，极具迷惑性）。只重载驱动、只重启应用都救不回来。
    if [ "$fails" -ge 3 ]; then
        echo "[supervisor] consecutive=$fails -> PCIe rescan + driver reload" >&2
        rmmod pango_pci_driver 2>/dev/null
        echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null
        sleep 1
        echo 1 > /sys/bus/pci/rescan 2>/dev/null
        sleep 2
        insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null
        ls /dev/pango_pci_driver > /dev/null 2>&1 && echo "[supervisor] driver reloaded" >&2
        fails=0
        sleep 2
    fi
    sleep 3
done
