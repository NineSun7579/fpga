#!/bin/bash
# 每 5 分钟截一张 3568 屏幕（验证 HDMI/光口链路的显示成果）
# 用法: sudo setsid bash shot_every5.sh &    （需要 root：ffmpeg 要访问 :0 显示）
# 截图目录: /userdata/shots/hdmi_时间戳.png（只保留最近 24 张）
mkdir -p /userdata/shots
export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
while true; do
    ts=$(date +%Y%m%d_%H%M%S)
    ffmpeg -nostdin -loglevel error -y -f x11grab -video_size 1920x1080 -i :0.0 -frames:v 1 "/userdata/shots/hdmi_$ts.png" 2>/dev/null
    ls -1t /userdata/shots/hdmi_*.png 2>/dev/null | tail -n +25 | xargs -r rm -f
    sleep 300
done
