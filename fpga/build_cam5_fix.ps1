$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$bin = 'C:\pango\PDS_2022.2-SP6.4\bin'
$work = Join-Path $root 'project_cam5_fix_build02'
if (Get-Process pds,pds_shell -ErrorAction SilentlyContinue) { throw 'PDS is already running' }
if (Test-Path $work) { throw 'Build directory exists; preserve it and choose a new directory' }
New-Item -ItemType Directory -Path $work | Out-Null
Copy-Item (Join-Path $root 'project\project.pds') (Join-Path $work 'project.pds')
Copy-Item (Join-Path $root 'project\ipcore') (Join-Path $work 'ipcore') -Recurse
& "$bin\pds_shell.exe" -project "$work\project.pds" -run pnr -work_dir $work *> "$work\cam5_pnr.log"
if ($LASTEXITCODE -ne 0) { throw "PNR failed: $LASTEXITCODE" }
if (Select-String -Path "$work\cam5_pnr.log" -Pattern '^E:|Program Error Out') { throw 'PNR log contains an error' }
& "$bin\pds_shell.exe" -project "$work\project.pds" -run gen_bit_stream -work_dir $work *> "$work\cam5_bitgen.log"
if ($LASTEXITCODE -ne 0) { throw "Bitstream generation failed: $LASTEXITCODE" }
if (Select-String -Path "$work\cam5_bitgen.log" -Pattern '^E:|Program Error Out') { throw 'Bitstream log contains an error' }
Get-FileHash "$work\generate_bitstream\top.sbit" -Algorithm SHA256
