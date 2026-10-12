Set-Location "C:\Users\NineSun\Desktop\ov56401\project"
$py = "C:\Users\NineSun\anaconda3\python.exe"
$sbitSrc = "project_kf\generate_bitstream\top.sbit"

$s = Get-Item $sbitSrc -ErrorAction SilentlyContinue
if (-not ($s -and $s.Length -gt 3000000)) { Write-Output "SBIT_NOT_READY"; exit 1 }
Write-Output ("SBIT_READY " + $s.LastWriteTime + " " + [int]($s.Length/1KB) + "KB")

New-Item -ItemType Directory -Force -Path bitstream_2026-09-25_kf_kfen0 | Out-Null
Copy-Item $sbitSrc bitstream_2026-09-25_kf_kfen0\top.sbit -Force
Write-Output "copied"

Write-Output "=== link down ==="
& $py tools\_sh5.py "@tools/_trec.sh" 150 2>&1 | Select-String -Pattern 'rmmod rc|remove rc'
Write-Output "=== burn kfen0 ==="
& $py tools\burn_now.py flash_kf_kfen0.tcl 2>&1 | Select-Object -Last 3
Write-Output "=== link up + measure ==="
& $py tools\_sh5.py "@tools/_trec2.sh" 300 2>&1 | Select-String -Pattern 'insmod rc|bound|cam[12][AB] |autocorr|procs|__R2_DONE__'
Write-Output "=== screenshot ==="
& $py tools\_sh5.py "cd /tmp; DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/qk.png 2>/dev/null; ffmpeg -y -loglevel error -i /tmp/qk.png -q:v 3 /tmp/qk.jpg; md5sum /tmp/qk.jpg; echo __QK__" 150 2>&1 | Select-String -Pattern 'qk.jpg|__QK__'
& $py tools\_pull5.py /tmp/qk.jpg kfen0_state.jpg 2>&1 | Select-Object -Last 1
Write-Output "KFEN0_CHAIN_DONE"
