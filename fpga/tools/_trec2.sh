echo __R2_START__
echo 1 > /sys/bus/pci/rescan
sleep 3
insmod /root/ov5640/pango_pci_driver.ko
echo "insmod rc=$?"
sleep 4
echo -n 'bound: '
ls /sys/bus/pci/devices/0002:21:00.0/driver 2>&1 | head -1
echo ---per---
python3 /tmp/per.py 2>&1
echo ---restart-camview---
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null &
sleep 14
echo -n 'camview procs: '
ps aux | grep -a './camview' | grep -v grep | wc -l
echo ---dmesg---
dmesg | tail -3
echo __R2_DONE__
