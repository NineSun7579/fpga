$ErrorActionPreference = 'Stop'
$simBin = 'C:\modeltech64_10.6e\win64'
$rtlRoot = Join-Path $PSScriptRoot '..\..\..\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl'
Push-Location $PSScriptRoot
try {
    & 'C:\Users\NineSun\anaconda3\python.exe' verify_production.py
    if ($LASTEXITCODE -ne 0) { throw 'production audit failed' }
    & "$simBin\vlib.exe" production_work
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
    & "$simBin\vlog.exe" -work production_work -suppress 2388 "$rtlRoot\power_on_delay.v" "$rtlRoot\reg_config.v" "$rtlRoot\i2c_com.v" "$rtlRoot\cam2_merge.v" "$rtlRoot\video_async_fifo.v" legacy_reg_config.v legacy_i2c_com.v
    if ($LASTEXITCODE -ne 0) { throw 'production RTL compile failed' }
    & "$simBin\vlog.exe" -work production_work -sv actual_top_reset_extracted.sv tb_config_startup.sv tb_merge_reset.sv tb_power_startup.sv tb_sys_reset.sv
    if ($LASTEXITCODE -ne 0) { throw 'test compile failed' }
    foreach ($testName in @('tb_config_startup', 'tb_merge_reset', 'tb_power_startup', 'tb_sys_reset')) {
        $logName = "production_$testName.log"
        & "$simBin\vsim.exe" -c -l $logName "production_work.$testName" -do 'onbreak {quit -code 1}; onerror {quit -code 1}; run -all; quit -code 0'
        if ($LASTEXITCODE -ne 0) { throw "$testName failed" }
        $logBytes = [System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $logName))
        if (-not [System.Text.Encoding]::ASCII.GetString($logBytes).Contains('TEST PASS')) { throw "$testName missing PASS" }
    }
    $verifiedHashes = Get-Content production_hashes.json -Raw | ConvertFrom-Json
    foreach ($entry in $verifiedHashes.PSObject.Properties) {
        if ($entry.Name -eq 'sensor_table') { continue }
        $hashPath = Join-Path $rtlRoot $entry.Name
        if ($entry.Name -eq 'hdmi_ddr_ov5640_top.v' -and $env:TOP_RESET_CANDIDATE) { $hashPath = $env:TOP_RESET_CANDIDATE }
        $afterHash = (Get-FileHash $hashPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($afterHash -ne $entry.Value) { throw "Production changed during verification: $($entry.Name)" }
    }
    Write-Output 'PRODUCTION VERIFICATION PASS: all four simulations, exact candidate/top audit, hashes unchanged across run'
} finally { Pop-Location }
