$ErrorActionPreference = 'Stop'
$work = 'C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test\ov5640_sfp480p_test'
$tools = 'C:\Users\NineSun\Desktop\ov56401\project\tools'
$exe = 'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe'
if (Get-Process pds_shell,pds -ErrorAction SilentlyContinue) { throw 'PDS already running' }
$dest = Join-Path $work ('bitstream_merge_recovery_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $dest | Out-Null
Write-Host "BUILD_DIRECTORY: $dest"
Write-Host 'Building all current 50K repairs; live PDS output follows.'
Copy-Item "$work\build.pds" "$dest\build.pds"
& 'C:\Users\NineSun\anaconda3\python.exe' "$tools\snapshot_50k_sources.py" $work $dest
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
foreach ($name in 'compile','synthesize','device_map','place_route','generate_bitstream','generate_netlist') {
    $dir = Join-Path $work $name
    if (Test-Path $dir) { Move-Item $dir (Join-Path $dest ('previous_' + $name)) }
}
& $exe -project "$work\build.pds" -run pnr -work_dir $work 2>&1 | Tee-Object -FilePath "$dest\pnr.log"
if ($LASTEXITCODE -ne 0) { throw "PnR failed: $dest\pnr.log" }
if (Select-String -Path "$dest\pnr.log" -Pattern '^E:' -Quiet) {
    throw "PDS reported an error despite returning success: $dest\pnr.log"
}
if (Select-String -Path "$dest\pnr.log" -Pattern 'Design net mrg_clk is routed by general path' -Quiet) {
    throw "Merge clock still uses general routing: $dest\pnr.log"
}
Copy-Item "$work\place_route\clock_utilization.txt" $dest
$summary = Join-Path $work 'place_route\hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt'
if (-not (Test-Path $summary)) { throw "PnR did not produce timing report: $dest\pnr.log" }
Copy-Item $summary $dest
if ((Get-Content $summary -Raw) -notmatch 'Design Summary : All Constraints Met\.') {
    throw "Timing constraints failed: $dest"
}
$timingText = Get-Content $summary -Raw
foreach ($clock in 'mrg_clk','p_clk2core_tx_2','cmos1_pclk_16bit','cmos2_pclk_16bit','clk_25M','cam1_sccb','cam2_sccb') {
    if ($timingText -notmatch "(?m)^\s*$clock\s+$clock\s+") {
        throw "Clock missing from timing summary: $clock"
    }
}
& $exe -project "$work\build.pds" -run gen_bit_stream -work_dir $work 2>&1 | Tee-Object -FilePath "$dest\bit.log"
if ($LASTEXITCODE -ne 0) { throw "Bit generation failed: $dest\bit.log" }
Copy-Item "$work\generate_bitstream\hdmi_ddr_ov5640_top.sbit" $dest
Write-Output "BUILD_ARTIFACT: $dest\hdmi_ddr_ov5640_top.sbit"
Get-FileHash "$dest\hdmi_ddr_ov5640_top.sbit" -Algorithm SHA256
