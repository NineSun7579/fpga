#!/bin/bash
# Launch detview GUI on the RK3568 X display, screenshot it, then stop it.
export DISPLAY=:0
export XDG_RUNTIME_DIR=/tmp/runtime-root
mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
cd /root/ov5640 || exit 1
pkill -f 'detview/detview' 2>/dev/null
sleep 1
setsid ./detview/detview >/tmp/dv_gui.log 2>&1 </dev/null &
DVPID=$!
sleep 12
echo "--- detview processes ---"
ps aux | grep 'detview/detview' | grep -v grep | head -3
echo "--- screenshot ---"
./qshot/qshot /tmp/rk_detview.png 1024
chmod 644 /tmp/rk_detview.png
ls -l /tmp/rk_detview.png
echo "--- detview gui log ---"
tail -8 /tmp/dv_gui.log
pkill -f 'detview/detview' 2>/dev/null
echo "--- stopped ---"
