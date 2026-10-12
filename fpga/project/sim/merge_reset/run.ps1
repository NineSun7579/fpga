$ErrorActionPreference = 'Stop'
$simBin = 'C:\modeltech64_10.6e\win64'
$rtlRoot = Join-Path $PSScriptRoot '..\..\..\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl'
Push-Location $PSScriptRoot
try {
    & "$simBin\vlib.exe" work
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
    & "$simBin\vlog.exe" -suppress 2388 "$rtlRoot\cam2_merge.v" "$rtlRoot\video_async_fifo.v" "$rtlRoot\power_on_delay.v"
    if ($LASTEXITCODE -ne 0) { throw 'RTL vlog failed' }
    & "$simBin\vlog.exe" -sv reset_candidate.sv tb_merge_reset.sv tb_power_startup.sv
    if ($LASTEXITCODE -ne 0) { throw 'vlog failed' }
    foreach ($testName in @('tb_merge_reset', 'tb_power_startup')) {
        & "$simBin\vsim.exe" -c -voptargs=+acc -l "$testName.log" "work.$testName" -do 'onbreak {quit -code 1}; onerror {quit -code 1}; run -all; quit -code 0'
        if ($LASTEXITCODE -ne 0) { throw "$testName failed" }
        $logBytes = [System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot "$testName.log"))
        if (-not [System.Text.Encoding]::ASCII.GetString($logBytes).Contains('TEST PASS')) { throw "$testName missing PASS" }
    }
} finally { Pop-Location }
