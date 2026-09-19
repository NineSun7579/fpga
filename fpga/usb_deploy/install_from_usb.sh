#!/bin/bash
# install_from_usb.sh -- 在 RK3568 上从 U 盘安装并启动 camview
#
# 用法(板子桌面终端里, 或串口):
#   bash /media/*/*/install_from_usb.sh
#
# 做四件事:
#   1) 复制源码到 /root/ov5640/camview
#   2) 板上编译 (qmake + make)
#   3) 重载 PCIe 驱动(烧录后必须, 否则 DMA 死锁)
#   4) 启动显示守护
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST=/root/ov5640/camview

echo "== 1. 复制源码 =="
mkdir -p "$DEST"
if [ -d "$HERE/camview" ]; then
    cp -f "$HERE/camview/main.cpp" "$HERE/camview/camview.pro" "$DEST/"
    cp -f "$HERE/camview/run_camview.sh" /root/ov5640/run_camview.sh
    chmod +x /root/ov5640/run_camview.sh
else
    # 脚本与源码同目录时的兜底
    cp -f "$HERE/main.cpp" "$HERE/camview.pro" "$DEST/" 2>/dev/null || true
fi
ls -la "$DEST"/main.cpp

echo "== 2. 编译 =="
pkill -f run_camview.sh 2>/dev/null || true
pkill -f camview 2>/dev/null || true
sleep 1
cd "$DEST"
rm -f camview Makefile *.o moc_* .qmake.stash
/usr/lib/qt5/bin/qmake
make -j4
ls -la camview

echo "== 3. 重载 PCIe 驱动 =="
pkill -f camview 2>/dev/null || true
sleep 1
rmmod pango_pci_driver 2>/dev/null || true
echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null || true
sleep 1
echo 1 > /sys/bus/pci/rescan
sleep 2
insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null || true
ls -la /dev/pango_pci_driver || { echo "驱动设备节点缺失, 检查 insmod"; exit 1; }

echo "== 4. 启动显示 =="
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null &
sleep 10
ps aux | grep -a './camview' | grep -v grep | wc -l

echo "== 5. 窗口状态 =="
DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -root _NET_CLIENT_LIST 2>/dev/null \
  | grep -oE '0x[0-9a-f]+' \
  | while read id; do
      DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 xprop -id "$id" _NET_WM_NAME 2>/dev/null
    done | grep -a camview || echo "(未取到窗口标题)"

echo
echo "完成: HDMI 应显示相机画面; 键盘 E 切换 RAW/处理缓冲, H 看帮助"
