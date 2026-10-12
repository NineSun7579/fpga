#!/bin/bash
# board_bringup.sh -- one-shot bring-up + evidence collection on the RK3568.
# Runs detached (nohup) so console death does not interrupt it.
# Artifacts land in /root/ov5640/ (disk-backed, survives /tmp loss).
LOG=/root/ov5640/bringup.log
exec >> $LOG 2>&1
echo "=== bringup start $(date) uptime=$(cut -d' ' -f1 /proc/uptime) ==="

# 1. driver
lsmod | grep -q pango_pci_driver || insmod /root/ov5640/pango_pci_driver.ko
sleep 2
ls /dev/pango_pci_driver || { echo "NO DRIVER NODE"; exit 1; }

# 2. register probe (read path + camera counters)
timeout 40 python3 /tmp/dbg_probe2.py > /root/ov5640/dbg1.txt 2>&1
echo "probe rc=$?"

# 3. detview offscreen selftest (documented safe bring-up step)
cd /root/ov5640
QT_QPA_PLATFORM=offscreen timeout 25 ./detview/detview --selftest 12 --model 0 \
    > /root/ov5640/selftest.txt 2>&1
echo "selftest rc=$?"

# 4. viewer + interval screenshots
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh >/dev/null 2>&1 < /dev/null &
sleep 12
for i in 1 2 3 4 5 6; do
  DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 \
    /root/ov5640/qshot/qshot /root/ov5640/shot$i.png 900 >/dev/null 2>&1
  ffmpeg -y -loglevel error -i /root/ov5640/shot$i.png -q:v 3 /root/ov5640/shot$i.jpg \
    >/dev/null 2>&1
  echo "shot$i done $(date +%T)"
  [ $i -lt 6 ] && sleep 40
done

# 5. DDR captures (cam1/cam2 raw banks)
timeout 60 python3 /tmp/dualcap2.py > /root/ov5640/dualcap.txt 2>&1
echo "dualcap rc=$?"

echo "=== state summary ==="
ps aux | grep -a './camview' | grep -v grep | head -2
dmesg | tail -25
echo "=== bringup done $(date) ==="
touch /root/ov5640/BRINGUP_DONE
