$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path 'sim\cam3_i2c_pt' | Out-Null
Set-Location 'sim\cam3_i2c_pt'
if (Test-Path work) { Remove-Item -Recurse -Force work }
& 'C:\modeltech64_10.6e\win64\vlib.exe' work
& 'C:\modeltech64_10.6e\win64\vlog.exe' -work work -quiet '..\..\source\ov5640\ov5640_reg.v' '..\..\source\ov5640\ov5640\ov5640.v' '..\..\source\ov5640\ov5640_top.v'
$code = $LASTEXITCODE
Write-Output ("vlog exit=" + $code)
exit $code
