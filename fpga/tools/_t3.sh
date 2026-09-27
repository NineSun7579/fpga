echo __HELLO__
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
python3 /tmp/cap3.py 2>&1
echo ---jpeg---
ffmpeg -loglevel error -y -i /tmp/c1a.ppm -q:v 2 /tmp/c1.jpg
ffmpeg -loglevel error -y -i /tmp/c2a.ppm -q:v 2 /tmp/c2.jpg
ls -l /tmp/c1.jpg /tmp/c2.jpg
echo ---restart-camview---
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null &
sleep 13
echo -n 'camview procs: '
ps aux | grep -a './camview' | grep -v grep | wc -l
echo __OK__
