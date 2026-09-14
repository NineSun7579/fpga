#!/bin/bash
# run_detview.sh -- detview 显示守护启动脚本(补齐工程 run_camview.sh 角色)
# 单实例锁 + X11 环境变量 + 日志
APP=/root/ov5640/detview/detview
LOG=/root/ov5640/detview.log

if [ -f /tmp/detview.lock ] && kill -0 "$(cat /tmp/detview.lock)" 2>/dev/null; then
    echo "detview already running (pid $(cat /tmp/detview.lock))"
    exit 0
fi
rm -f /tmp/detview.lock

export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
cd /root/ov5640/detview
echo $$ > /tmp/detview.lock
exec "$APP" >> "$LOG" 2>&1
