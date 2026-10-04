#!/bin/bash
# bringup.sh —— FPGA 重烧/断电恢复后的板侧一键恢复
#   用法: sudo bash bringup.sh [detview 参数...]
#   例:   sudo bash bringup.sh --fullscreen --rotate-model zebra-rk3568-raw-dfl6,wb_v4_combo
# 步骤: 清理卡死实例 -> 驱动按需重载 -> PCIe remove/rescan -> 启动守护 -> 探针确认出流
cd "$(dirname "$0")" || exit 1

echo "[1/5] 清理残留 detview 实例..."
pkill -9 -x detview 2>/dev/null
sleep 1

echo "[2/5] 驱动状态..."
if lsmod | grep -q pango_pci_driver; then
    echo "  已加载 -> rmmod 后重新加载（位流重烧/复位后必做）"
    rmmod pango_pci_driver 2>/dev/null
else
    echo "  未加载 -> 直接加载"
fi
echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null
sleep 1
echo 1 > /sys/bus/pci/rescan 2>/dev/null
sleep 2
insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null
sleep 1
if ! ls /dev/pango_pci_driver >/dev/null 2>&1; then
    echo "FATAL: /dev/pango_pci_driver 未出现（检查 PCIe rescan / 位流是否已固化）"
    exit 1
fi
echo "  设备就绪: $(ls -l /dev/pango_pci_driver)"

echo "[3/5] 启动 detview 守护..."
rm -f /tmp/detview.lock /tmp/detview_supervisor.pid
setsid bash ./run_detview.sh "$@" > /tmp/detview_watch.log 2>&1 < /dev/null &
sleep 8
echo "  supervisor=$(cat /tmp/detview_supervisor.pid 2>/dev/null)"

echo "[4/5] 探针 15 秒..."
sleep 15
echo "panes=$(grep -ac '\[panes\]' /tmp/detview_watch.log) recover=$(grep -ac '\[recover\]' /tmp/detview_watch.log)"
grep -a '\[panes\]' /tmp/detview_watch.log | tail -2

echo "[5/5] 完成。日志: /tmp/detview_watch.log（守护会持续自愈：60s 无新帧或连续 6 次 ioctl 失败自动重启）"
