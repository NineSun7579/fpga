Set-Location "C:\Users\NineSun\Desktop\ov56401\project"
$py = "C:\Users\NineSun\anaconda3\python.exe"

$patch = @'
p = r'source\top.v'
d = open(p, 'rb').read()
d = d.replace(b".KF_EN         (1'b0)", b".KF_EN         (1'b1)")
open(p, 'wb').write(d)
print("MEDIAN_EN 1b0 =", d.count(b".MEDIAN_EN     (1'b0)"))
print("KF_EN     1b1 =", d.count(b".KF_EN         (1'b1)"))
'@
$patch | & $py -

Write-Output "=== link down ==="
& $py tools\_sh5.py "@tools/_trec.sh" 150 2>&1 | Select-String -Pattern 'rmmod rc|remove rc'
Write-Output "=== restore KF gate ==="
& $py tools\burn_now.py flash_kf_gate.tcl 2>&1 | Select-Object -Last 2
Write-Output "=== link up + camview ==="
& $py tools\_sh5.py "@tools/_trec2.sh" 300 2>&1 | Select-String -Pattern 'insmod rc|bound|cam1A  R|procs|__R2_DONE__'
Write-Output "FINAL_RESTORE_DONE"
