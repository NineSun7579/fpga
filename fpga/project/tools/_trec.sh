echo __R_START__
pkill -f run_camview.sh 2>/dev/null
pkill -x camview 2>/dev/null
sleep 2
timeout 20 rmmod pango_pci_driver
echo "rmmod rc=$?"
echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove
echo "remove rc=$?"
sleep 1
echo __R_DONE__
