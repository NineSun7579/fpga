$ErrorActionPreference = 'Continue'
$root = 'C:\Users\NineSun\Desktop\ov56401\project'
Set-Location $root

# 1) preserve the pre-rebuild bitstream (15:31, MEDIAN_EN=1 build)
$bak = Join-Path $root '_rollback_backup_20260925'
New-Item -ItemType Directory -Force -Path $bak | Out-Null
if (Test-Path 'project_kf\generate_bitstream\top.sbit') {
    Copy-Item 'project_kf\generate_bitstream\top.sbit' (Join-Path $bak 'project_kf_top_before_rebuild.sbit') -Force
}

# 2) clean stale build dirs (mandatory per project rules)
Remove-Item 'project_kf\compile','project_kf\synthesize','project_kf\device_map','project_kf\place_route','project_kf\generate_bitstream' -Recurse -Force -ErrorAction SilentlyContinue

# 3) synth + pnr
& 'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe' -project (Resolve-Path 'project_kf\project.pds') -run pnr -work_dir (Resolve-Path 'project_kf') *> 'project_kf\kf_pnr_rollback.log'
$rc1 = $LASTEXITCODE

# 4) bitstream generation
& 'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe' -project (Resolve-Path 'project_kf\project.pds') -run gen_bit_stream -work_dir (Resolve-Path 'project_kf') *> 'project_kf\kf_bitgen_rollback.log'
$rc2 = $LASTEXITCODE

Write-Output "PNR_RC=$rc1 BITGEN_RC=$rc2"
Get-ChildItem 'project_kf\generate_bitstream' -Force -ErrorAction SilentlyContinue | Select-Object Length,LastWriteTime,Name | Format-Table -AutoSize
