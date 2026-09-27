$ErrorActionPreference = 'Continue'
Set-Location 'sim\cam3_i2c_pt'
if (Test-Path work) { Remove-Item -Recurse -Force work }
& 'C:\modeltech64_10.6e\win64\vlib.exe' work
& 'C:\modeltech64_10.6e\win64\vlog.exe' -work work '..\..\source\ov5640\ov5640_reg.v' tb_ov5640_reg_pt.sv
if ($LASTEXITCODE -ne 0) { Write-Output 'COMPILE FAIL'; exit 1 }
& 'C:\modeltech64_10.6e\win64\vsim.exe' -c -do 'onerror {quit -code 1}; run -all; quit -code 0' work.tb_ov5640_reg_pt
$code = $LASTEXITCODE
Write-Output ("vsim exit=" + $code)
exit $code
