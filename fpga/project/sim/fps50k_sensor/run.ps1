$ErrorActionPreference = 'Stop'
$simBin = 'C:\modeltech64_10.6e\win64'
Push-Location $PSScriptRoot
try {
    & "$simBin\vlib.exe" margin_work
    if ($LASTEXITCODE -ne 0) { throw 'vlib failed' }
    & "$simBin\vlog.exe" -work margin_work -suppress 2388 power_on_delay.v reg_config.v i2c_com.v
    if ($LASTEXITCODE -ne 0) { throw 'RTL compile failed' }
    & "$simBin\vlog.exe" -work margin_work -sv '+incdir+.' tb_sensor_colorbar.sv
    if ($LASTEXITCODE -ne 0) { throw 'test compile failed' }
    foreach ($mode in @(0, 1)) {
        & "$simBin\vsim.exe" -c -l "mode_$mode.log" "-gCOLOR_BAR_TEST=$mode" margin_work.tb_sensor_colorbar -do 'onbreak {quit -code 1}; onerror {quit -code 1}; run -all; quit -code 0'
        if ($LASTEXITCODE -ne 0) { throw "mode $mode failed" }
        if (-not (Get-Content "mode_$mode.log" -Raw).Contains("TEST PASS mode=$mode")) { throw 'missing PASS' }
    }
} finally { Pop-Location }
