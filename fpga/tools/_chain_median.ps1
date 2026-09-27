Set-Location "C:\Users\NineSun\Desktop\ov56401\project"
$py = "C:\Users\NineSun\anaconda3\python.exe"
$sbitSrc = "project_kf\generate_bitstream\top.sbit"
$deadline = (Get-Date).AddMinutes(40)
Write-Output "waiting for bitstream..."
while ((Get-Date) -lt $deadline) {
    $s = Get-Item $sbitSrc -ErrorAction SilentlyContinue
    if ($s -and $s.Length -gt 3000000) { break }
    $n = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq 'pds_shell' }).Count
    if ($n -eq 0) { Write-Output "NO_PDS_RUNNING"; break }
    Start-Sleep -Seconds 15
}
$s = Get-Item $sbitSrc -ErrorAction SilentlyContinue
if (-not ($s -and $s.Length -gt 3000000)) {
    Write-Output "SBIT_NOT_READY"
    Get-Content project_kf\kf_bitgen_median.log -Tail 12 -ErrorAction SilentlyContinue
    exit 1
}
Write-Output ("SBIT_READY " + $s.LastWriteTime + " " + [int]($s.Length/1KB) + "KB")

New-Item -ItemType Directory -Force -Path bitstream_2026-09-25_kf_median | Out-Null
Copy-Item $sbitSrc bitstream_2026-09-25_kf_median\top.sbit -Force
Write-Output "copied to bitstream_2026-09-25_kf_median/top.sbit"

Write-Output "=== link down (rmmod + remove) ==="
& $py tools\_sh5.py "@tools/_trec.sh" 150 2>&1 | Select-String -Pattern '__R_|rmmod rc|remove rc'
Write-Output "=== burn ==="
& $py tools\burn_now.py flash_kf_median.tcl 2>&1 | Select-Object -Last 3
Write-Output "=== link up + measure + camview ==="
& $py tools\_sh5.py "@tools/_trec2.sh" 300 2>&1 | Select-String -Pattern '__R2_|insmod rc|bound|cam[12][AB] |autocorr|procs|__R2_DONE__'
Write-Output "=== screenshot ==="
& $py tools\_sh5.py "cd /tmp; DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 /root/ov5640/qshot/qshot /tmp/qm.png 2>/dev/null; ffmpeg -y -loglevel error -i /tmp/qm.png -q:v 3 /tmp/qm.jpg; md5sum /tmp/qm.jpg; echo __QM__" 150 2>&1 | Select-String -Pattern 'qm.jpg|__QM__'
& $py tools\_pull5.py /tmp/qm.jpg median_state.jpg 2>&1 | Select-Object -Last 1
Write-Output "MEDIAN_CHAIN_DONE"
