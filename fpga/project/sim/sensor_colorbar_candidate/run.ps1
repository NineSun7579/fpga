$ErrorActionPreference = 'Stop'
$simBin = 'C:\modeltech64_10.6e\win64'
Push-Location $PSScriptRoot
try {
    & "$simBin\vlib.exe" colorbar_work
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
    & "$simBin\vlog.exe" -work colorbar_work -suppress 2388 power_on_delay.v reg_config.v i2c_com.v
    if ($LASTEXITCODE -ne 0) { throw 'RTL compile failed' }
    & "$simBin\vlog.exe" -work colorbar_work -sv '+incdir+.' tb_sensor_colorbar.sv
    if ($LASTEXITCODE -ne 0) { throw 'test compile failed' }
    foreach ($mode in @(0, 1)) {
        & "$simBin\vsim.exe" -c -l "mode_$mode.log" "-gCOLOR_BAR_TEST=$mode" colorbar_work.tb_sensor_colorbar -do 'onbreak {quit -code 1}; onerror {quit -code 1}; run -all; quit -code 0'
        if ($LASTEXITCODE -ne 0) { throw "mode $mode failed" }
        if (-not (Get-Content "mode_$mode.log" -Raw).Contains("TEST PASS mode=$mode")) { throw 'missing PASS' }
    }
    $rtlRoot = Join-Path $PSScriptRoot '..\..\..\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl'
    $hashes = Get-Content production_hashes.json -Raw | ConvertFrom-Json
    foreach ($entry in $hashes.PSObject.Properties) {
        if ((Get-FileHash (Join-Path $rtlRoot $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
            throw "production changed: $($entry.Name)"
        }
    }
    Write-Output 'COLORBAR CANDIDATE PASS; production hashes unchanged'
} finally { Pop-Location }
