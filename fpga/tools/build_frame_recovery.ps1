$ErrorActionPreference = 'Stop'
$root = 'C:\Users\NineSun\Desktop\ov56401\project'
$work = Join-Path $root 'project_kf'
$exe = 'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe'
if (Get-Process pds_shell,pds -ErrorAction SilentlyContinue) { throw 'PDS already running' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dest = Join-Path $root ('bitstream_frame_recovery_' + $stamp)
New-Item -ItemType Directory -Path $dest | Out-Null
Copy-Item "$work\project.pds" "$dest\project.pds"
# Snapshot all actual source inputs before implementation, including constraints.
& 'C:\Users\NineSun\anaconda3\python.exe' "$root\tools\snapshot_recovery_sources.py" $dest
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
foreach ($name in 'compile','synthesize','device_map','place_route','generate_bitstream','generate_netlist') {
    $dir = Join-Path $work $name
    if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
}
& $exe -project "$work\project.pds" -run pnr -work_dir $work *> "$dest\pnr.log"
if ($LASTEXITCODE -ne 0) { throw "PnR failed: $dest\pnr.log" }
& $exe -project "$work\project.pds" -run gen_bit_stream -work_dir $work *> "$dest\bit.log"
if ($LASTEXITCODE -ne 0) { throw "Bitstream generation failed: $dest\bit.log" }
$bit = Join-Path $work 'generate_bitstream\top.sbit'
if (!(Test-Path $bit)) { throw 'Missing sbit' }
Copy-Item $bit $dest
Get-ChildItem "$work\place_route" -Filter '*.rpt' -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($work.Length + 1)
    $target = Join-Path $dest $relative
    New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
    Copy-Item $_.FullName $target
}
Write-Output "BUILD_ARTIFACT: $dest\top.sbit"
Get-FileHash "$dest\top.sbit" -Algorithm SHA256
