#!/bin/bash
# camview 板端构建+运行脚本 (RK3568)
# 用法: bash build_camview.sh build   -> qmake+make
#       bash build_camview.sh run     -> 前台运行(占串口终端输出)
#       bash build_camview.sh bg      -> 后台运行
set -e
cd /userdata/linaro/projects/RK3568/camview
if [ "$1" != "run" ] && [ "$1" != "bg" ]; then
    qmake
    make -j4
    echo BUILD_OK
fi
if [ "$1" = "run" ]; then
    export DISPLAY=:0
    export XAUTHORITY=/var/run/lightdm/root/:0
    exec ./camview
fi
if [ "$1" = "bg" ]; then
    export DISPLAY=:0
    export XAUTHORITY=/var/run/lightdm/root/:0
    nohup ./camview > /userdata/linaro/projects/RK3568/camview.log 2>&1 &
    echo "BG started pid $!"
    sleep 3
    tail -5 /userdata/linaro/projects/RK3568/camview.log
fi
