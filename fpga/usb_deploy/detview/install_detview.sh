#!/bin/bash
# install_detview.sh -- 在 RK3568 上从 U 盘安装并启动 detview(检测画框)
#
# 用法(板子桌面终端里, 或串口):
#   bash /media/*/*/detview/install_detview.sh
#
# 做五件事:
#   1) 复制源码到 /root/ov5640/detview, 模型到 /root/ov5640/models, 库到 /root/ov5640/lib
#   2) 板上编译 (qmake + make)
#   3) 环境自检: rknpu 内核驱动 / qmake / 设备节点
#   4) 重载 PCIe 驱动(烧录后必须, 否则 DMA 死锁)
#   5) 运行自检: ./detview --selftest 12 --model 0
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APP=/root/ov5640/detview
MODELS=/root/ov5640/models
LIB=/root/ov5640/lib

echo "== 1. 复制文件 =="
mkdir -p "$APP" "$MODELS" "$LIB"
cp -f "$HERE"/*.cpp "$HERE"/*.h "$HERE"/*.pro "$APP/"
cp -f "$HERE"/models/*.rknn "$MODELS/" 2>/dev/null || echo "(本介质无模型, 保留板上已有)"
cp -f "$HERE"/lib/librknnrt.so "$LIB/" 2>/dev/null || echo "(本介质无 librknnrt.so, 保留板上已有)"
ls -la "$MODELS"/ | head -8
ls -la "$LIB"/librknnrt.so

echo "== 2. 编译 =="
pkill -f "detview" 2>/dev/null || true
sleep 1
cd "$APP"
rm -f detview Makefile *.o moc_* .qmake.stash
/usr/lib/qt5/bin/qmake
make -j4
ls -la detview

echo "== 3. 环境自检 =="
dmesg | grep -i rknpu | tail -3 || echo "WARN: dmesg 无 rknpu 痕迹(内核驱动可能缺失)"
[ -d /sys/kernel/debug/rknpu ] && cat /sys/kernel/debug/rknpu/version 2>/dev/null || true
ls -la /dev/pango_pci_driver || { echo "pango 设备节点缺失"; }

echo "== 4. 重载 PCIe 驱动 =="
rmmod pango_pci_driver 2>/dev/null || true
echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove 2>/dev/null || true
sleep 1
echo 1 > /sys/bus/pci/rescan
sleep 2
insmod /root/ov5640/pango_pci_driver.ko 2>/dev/null || true
ls -la /dev/pango_pci_driver

echo "== 5. 自检运行(12 秒, 模型 0=zebra_3cls_e2e) =="
cd "$APP"
./detview --selftest 12 --model 0
echo
echo "完成: 自检 PASS 后可启动界面: DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 $APP/detview"
