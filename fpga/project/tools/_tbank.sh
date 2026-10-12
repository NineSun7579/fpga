echo __BANK_START__
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
echo -n 'bound: '
ls /sys/bus/pci/devices/0002:21:00.0/driver 2>&1 | head -1
echo ---per-run1---
python3 /tmp/per.py 2>&1
echo ---per-run2---
python3 /tmp/per.py 2>&1
echo ---jpeg-cam1-A-vs-B---
cd /tmp
python3 /tmp/cap3.py 2>&1
for n in c1a c1b c2a c2b; do
  if [ -f /tmp/$n.ppm ]; then ffmpeg -y -loglevel error -i /tmp/$n.ppm -q:v 2 /tmp/$n.jpg; fi
done
ls -l /tmp/c1a.jpg /tmp/c1b.jpg /tmp/c2a.jpg /tmp/c2b.jpg 2>&1
echo ---restart-camview---
rm -f /tmp/camview.lock
setsid nohup /root/ov5640/run_camview.sh > /dev/null 2>&1 < /dev/null &
sleep 14
echo -n 'camview procs: '
ps aux | grep -a './camview' | grep -v grep | wc -l
echo __BANK_DONE__
