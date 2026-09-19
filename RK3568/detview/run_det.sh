#!/bin/bash
# run_det.sh [--model SUBSTR | --model-index N] : start detview detached on the local X display
export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
cd /root/npu/detview || exit 1
pkill -f /root/npu/detview/detview 2>/dev/null
sleep 1
exec /root/npu/detview/detview "$@" > /root/npu/detview/run.log 2>&1
