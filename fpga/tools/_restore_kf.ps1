Set-Location "C:\Users\NineSun\Desktop\ov56401\project"
$py = "C:\Users\NineSun\anaconda3\python.exe"
Write-Output "=== link down ==="
& $py tools\_sh5.py "@tools/_trec.sh" 150 2>&1 | Select-String -Pattern 'rmmod rc|remove rc'
Write-Output "=== restore KF gate ==="
& $py tools\burn_now.py flash_kf_gate.tcl 2>&1 | Select-Object -Last 3
Write-Output "=== link up + camview ==="
& $py tools\_sh5.py "@tools/_trec2.sh" 300 2>&1 | Select-String -Pattern 'insmod rc|bound|cam1A  R|procs|__R2_DONE__'
Write-Output "=== screenshot ==="
& $py tools\_sh5.py "cd /tmp; DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/qr.png 2>/dev/null; ffmpeg -y -loglevel error -i /tmp/qr.png -q:v 3 /tmp/qr.jpg; md5sum /tmp/qr.jpg; echo __QR__" 150 2>&1 | Select-String -Pattern 'qr.jpg|__QR__'
& $py tools\_pull5.py /tmp/qr.jpg restore_state.jpg 2>&1 | Select-Object -Last 1
Write-Output "RESTORE_DONE"
