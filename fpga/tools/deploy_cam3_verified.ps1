param([Parameter(Mandatory=$true)][string]$Sbit)
$ErrorActionPreference='Stop'
$root='C:\Users\NineSun\Desktop\ov56401\project'
Set-Location $root
if (Get-Process pds_shell,pds -ErrorAction SilentlyContinue) { throw 'PDS running; cannot program' }
if (!(Test-Path -LiteralPath $Sbit)) { throw 'Missing bitstream' }
python tools\sshx.py "killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 2; rmmod pango_pci_driver || exit 1; if test -e /sys/bus/pci/devices/0002:21:00.0/remove; then echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove; fi" --sudo --tries 2 --timeout 30
if ($LASTEXITCODE -ne 0) { throw 'PCIe preparation failed' }
& powershell -ExecutionPolicy Bypass -File .\flash_any.ps1 -Sbit $Sbit -LogPrefix flash_cam3_verified
if ($LASTEXITCODE -ne 0) { throw 'FPGA programming failed' }
python tools\validate_cam3_display.py
if ($LASTEXITCODE -ne 0) { throw 'RK3568 validation script failed' }
