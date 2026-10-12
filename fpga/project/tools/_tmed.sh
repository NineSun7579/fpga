echo __M_START__
pkill -f run_camview.sh 2>/dev/null
pkill -x camview 2>/dev/null
sleep 2
timeout 20 rmmod pango_pci_driver
echo "rmmod rc=$?"
echo 1 > /sys/bus/pci/rescan
sleep 3
insmod /root/ov5640/pango_pci_driver.ko
echo "insmod rc=$?"
sleep 4
echo ---per---
python3 /tmp/per.py 2>&1
echo ---cap3---
python3 /tmp/cap3.py 2>&1
echo ---jpeg---
cd /tmp; ffmpeg -y -loglevel error -i /tmp/c1a.ppm -q:v 2 /tmp/m1.jpg
ls -l /tmp/m1.jpg
echo ---restart-camview---
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null &
sleep 13
echo -n 'camview procs: '
ps aux | grep -a './camview' | grep -v grep | wc -l
echo __M_DONE__
