#!/bin/bash
export DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0
cd /root/ov5640/camview || exit 1
cp /tmp/main_new.cpp ./main.cpp
echo "=== build ==="
make -j4 2>&1 | grep -iE '\berror\b|Error [0-9]' | head -20
ls -la camview

pkill -9 -x camview 2>/dev/null; pkill -9 -f 'run_camview[.]sh' 2>/dev/null; sleep 2
rmmod pango_pci_driver 2>/dev/null; sleep 1; insmod /root/ov5640/pango_pci_driver.ko; sleep 1

CAMVIEW_HUDDUMP=1 setsid nohup ./camview > /tmp/fps3.log 2>&1 < /dev/null &
sleep 9
cd /root/ov5640/qshot
./qshot /tmp/fps3.png 1920 >/dev/null 2>&1
chmod 644 /tmp/fps3.png
ls -la /tmp/fps3.png /tmp/camview_hud.png 2>/dev/null
grep -a 'camview_gl_renderer' /tmp/fps3.log | head -1
grep -a camview_fps /tmp/fps3.log | tail -2
echo DONE
