$ErrorActionPreference = 'Stop'
$root = 'C:\Users\NineSun\Desktop\ov56401\project'
$work = Join-Path $root 'project_kf'
$exe = 'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe'
if (Get-Process pds_shell,pds -ErrorAction SilentlyContinue) { throw 'PDS already running' }
foreach ($name in 'compile','synthesize','device_map','place_route','generate_bitstream','generate_netlist') {
    $dir = Join-Path $work $name
    if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
}
& $exe -project "$work\project.pds" -run pnr -work_dir $work *> "$root\cam3_init48_pnr.log"
if ($LASTEXITCODE -ne 0) { throw 'PnR failed; see cam3_init48_pnr.log' }
if (Get-Process pds_shell,pds -ErrorAction SilentlyContinue) { throw 'PDS remains running' }
& $exe -project "$work\project.pds" -run gen_bit_stream -work_dir $work *> "$root\cam3_init48_bit.log"
if ($LASTEXITCODE -ne 0) { throw 'Bitstream generation failed' }
$bit = Join-Path $work 'generate_bitstream\top.sbit'
if (!(Test-Path $bit)) { throw 'Missing sbit' }
$dest = Join-Path $root ('bitstream_cam3_init48_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $dest | Out-Null
Copy-Item $bit $dest
Copy-Item "$root\source\ov5640\ovreg_axil_decode.v" $dest
Copy-Item "$root\source\ov5640\ov5640_ddr\ov5640_ddr_w.v" $dest
Copy-Item "$root\source\axi_crossbar\ddr_w_arb.v" $dest
Copy-Item "$root\source\constraints\ov5640.fdc" $dest
Copy-Item "$root\source\constraints\clock.fdc" $dest
Write-Output "BUILD_ARTIFACT: $dest\top.sbit"
Get-FileHash "$dest\top.sbit" -Algorithm SHA256
