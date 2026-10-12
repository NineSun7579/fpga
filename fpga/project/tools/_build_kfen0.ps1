Set-Location "C:\Users\NineSun\Desktop\ov56401\project"
$py = "C:\Users\NineSun\anaconda3\python.exe"

$patch = @'
import shutil
p = r'source\top.v'
shutil.copyfile(p, r'source\top.v.bak7_before_kfen0')
d = open(p, 'rb').read()
d = d.replace(b".MEDIAN_EN     (1'b1)", b".MEDIAN_EN     (1'b0)")
d = d.replace(b".KF_EN         (1'b1)", b".KF_EN         (1'b0)")
open(p, 'wb').write(d)
print("MEDIAN_EN 1b0 =", d.count(b".MEDIAN_EN     (1'b0)"))
print("KF_EN     1b0 =", d.count(b".KF_EN         (1'b0)"))
'@
$patch | & $py -

foreach ($d in @('compile','synthesize','device_map','place_route')) {
  $p = Join-Path 'project_kf' $d
  if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
& C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe -project C:/Users/NineSun/Desktop/ov56401/project/project_kf/project.pds -run pnr -work_dir C:/Users/NineSun/Desktop/ov56401/project/project_kf *> project_kf\kf_pnr_kfen0.log
Write-Output "PNR_EXIT=$LASTEXITCODE"
& C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe -project C:/Users/NineSun/Desktop/ov56401/project/project_kf/project.pds -run gen_bit_stream -work_dir C:/Users/NineSun/Desktop/ov56401/project/project_kf *> project_kf\kf_bitgen_kfen0.log
Write-Output "BITGEN_EXIT=$LASTEXITCODE"
Write-Output "KFEN0_BUILD_DONE"
