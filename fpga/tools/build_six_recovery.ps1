param([switch]$AllowParallel50K)
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\NineSun\Desktop\ov56401\project'
$work = Join-Path $root 'project_build'
$exe = 'C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe'
$activePds = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('pds_shell.exe','pds.exe') })
$otherWork = 'C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test\ov5640_sfp480p_test'
foreach ($process in $activePds) {
    $command = $process.CommandLine
    if (-not $AllowParallel50K -or $process.Name -eq 'pds.exe' -or -not $command) {
        throw 'PDS already running; parallel execution requires an identified independent 50K project'
    }
    $normalized = $command.Replace('/', '\')
    if ($normalized.IndexOf($work, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $normalized.IndexOf($otherWork, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "PDS process $($process.ProcessId) is not the permitted independent 50K build"
    }
}
$dest = Join-Path $root ('bitstream_six_recovery_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $dest | Out-Null
Write-Host "BUILD_DIRECTORY: $dest"
Write-Host "100H work directory: $work; live PDS output follows."
Copy-Item "$work\project.pds" "$dest\project.pds"
& 'C:\Users\NineSun\anaconda3\python.exe' "$root\tools\snapshot_six_sources.py" $dest
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
foreach ($name in 'compile','synthesize','device_map','place_route','generate_bitstream','generate_netlist') {
    $dir = Join-Path $work $name
    if (Test-Path $dir) { Move-Item $dir (Join-Path $dest ('previous_' + $name)) }
}
& $exe -project "$work\project.pds" -run pnr -work_dir $work 2>&1 | Tee-Object -FilePath "$dest\pnr.log"
if ($LASTEXITCODE -ne 0) { throw "PnR failed: $dest\pnr.log" }
if (Select-String -Path "$dest\pnr.log" -Pattern '^E:' -Quiet) { throw "PDS reported an error: $dest\pnr.log" }
$summary = Join-Path $work 'place_route\top_timing_summary_after_hold_fix.txt'
if (-not (Test-Path $summary)) { throw "PnR did not produce timing report: $dest\pnr.log" }
Copy-Item "$work\place_route\*timing*" $dest -ErrorAction SilentlyContinue
& 'C:\Users\NineSun\anaconda3\python.exe' "$root\tools\audit_six_timing.py" $summary
if ($LASTEXITCODE -ne 0) { throw "Timing constraints failed: $dest" }
& $exe -project "$work\project.pds" -run gen_bit_stream -work_dir $work 2>&1 | Tee-Object -FilePath "$dest\bit.log"
if ($LASTEXITCODE -ne 0) { throw "Bitstream generation failed: $dest\bit.log" }
$bit = Join-Path $work 'generate_bitstream\top.sbit'
if (!(Test-Path $bit)) { throw 'Missing sbit' }
Copy-Item $bit $dest
Write-Output "BUILD_ARTIFACT: $dest\top.sbit"
Get-FileHash "$dest\top.sbit" -Algorithm SHA256
