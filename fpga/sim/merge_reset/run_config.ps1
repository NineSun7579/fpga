$ErrorActionPreference = 'Stop'
$simBin = 'C:\modeltech64_10.6e\win64'
$rtlRoot = Join-Path $PSScriptRoot '..\..\..\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl'
Push-Location $PSScriptRoot
try {
    & 'C:\Users\NineSun\anaconda3\python.exe' prepare_config_candidate.py
    if ($LASTEXITCODE -ne 0) { throw 'prepare failed' }
    & "$simBin\vlib.exe" config_work
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
    & "$simBin\vlog.exe" -work config_work -suppress 2388 "$rtlRoot\power_on_delay.v" candidate_reg_config.v candidate_i2c_com.v legacy_reg_config.v legacy_i2c_com.v
    if ($LASTEXITCODE -ne 0) { throw 'RTL compile failed' }
    & "$simBin\vlog.exe" -work config_work -sv tb_config_startup.sv
    if ($LASTEXITCODE -ne 0) { throw 'test compile failed' }
    & "$simBin\vsim.exe" -c -l tb_config_startup.log config_work.tb_config_startup -do 'onbreak {quit -code 1}; onerror {quit -code 1}; run -all; quit -code 0'
    if ($LASTEXITCODE -ne 0) { throw 'config simulation failed' }
    $logBytes = [System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'tb_config_startup.log'))
    if (-not [System.Text.Encoding]::ASCII.GetString($logBytes).Contains('TEST PASS')) { throw 'missing PASS' }
} finally { Pop-Location }
