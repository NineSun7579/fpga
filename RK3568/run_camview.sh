#!/bin/bash
# Q/ESC exits 0. Any nonzero exit, including a driver-induced SIGSEGV, recovers.
exec 9>/tmp/camview.lock
flock -n 9 || exit 0

export DISPLAY=:0
export XAUTHORITY=/var/run/lightdm/root/:0
cd /root/ov5640/camview || exit 1

while true; do
    ./camview
    rc=$?
    [ "$rc" -eq 0 ] && exit 0

    sleep 1
    rmmod pango_pci_driver 2>/dev/null || true
    sleep 1
    insmod /root/ov5640/pango_pci_driver.ko || exit 1
    sleep 2
done
