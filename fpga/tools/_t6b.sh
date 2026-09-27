echo __B_START__
echo 1 > /sys/bus/pci/rescan
sleep 3
insmod /root/ov5640/pango_pci_driver.ko
echo "insmod rc=$?"
sleep 4
python3 /tmp/cap3.py 2>&1
echo ---per---
python3 /tmp/per.py 2>&1
echo ---jpeg---
cd /tmp; ffmpeg -y -loglevel error -i /tmp/c1a.ppm -q:v 2 /tmp/b1.jpg
cd /tmp; ffmpeg -y -loglevel error -i /tmp/c2a.ppm -q:v 2 /tmp/b2.jpg
ls -l /tmp/b1.jpg /tmp/b2.jpg
echo __B_DONE__
