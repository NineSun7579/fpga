lspci -vvv -s 0002:21:00.0 > /tmp/l2.txt 2>&1
grep -aE 'LnkSta|UESta|CESta|Region|MSI:' /tmp/l2.txt
echo '--- driver state ---'
grep -i pango /proc/interrupts
echo '--- last dmesg ---'
dmesg | tail -8
