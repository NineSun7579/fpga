echo __HELLO__
pkill -x camview 2>/dev/null
pkill -f run_camview.sh 2>/dev/null
sleep 2
cd /root/ov5640/detview && QT_QPA_PLATFORM=offscreen ./detview --selftest 6 --model 0 2>&1 | tail -6
echo ---ppm---
ls -l /root/ov5640/detview_selftest.ppm
ffmpeg -loglevel error -y -i /root/ov5640/detview_selftest.ppm -vf crop=640:480:0:80 -q:v 3 /tmp/dv1.jpg
ls -l /tmp/dv1.jpg
md5sum /tmp/dv1.jpg
echo __OK__
