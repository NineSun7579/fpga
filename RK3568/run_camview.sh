#!/bin/bash
# camview 守护(单实例锁): 退出后1秒自动重启
[ -f /tmp/camview.lock ] && exit 0
touch /tmp/camview.lock
cd /userdata/linaro/projects/RK3568/camview
export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
while true; do
    ./camview
    echo "$(date) exited rc=$? restart" >> /userdata/linaro/projects/RK3568/camview.log
    sleep 1
done
