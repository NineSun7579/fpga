$ErrorActionPreference = 'Stop'
$taskRoot20 = Split-Path $PSScriptRoot -Parent
$taskBuild20 = Join-Path (Split-Path $taskRoot20 -Parent) 'build04_functional_route04'
$taskPython20 = 'C:\Users\NineSun\anaconda3\python.exe'
$taskStart20 = Join-Path $PSScriptRoot 'serial_started.json'
if (Test-Path $taskStart20) { throw 'Never repeat serial continuation20' }
$taskBusy20 = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(pds|pds_shell|pnr|ta)\.exe$' -or
    ($_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'resume_io_verify20.py|functional_delivery_execute20.*runner.py') })
if ($taskBusy20.Count -gt 0) { throw 'Vendor or continuation20 process still busy' }
@{utc=[DateTime]::UtcNow.ToString('o'); goal_complete=$false} | ConvertTo-Json | Set-Content -Encoding UTF8 $taskStart20
Write-Output 'Starting verify20: BSDL-verified IO acceptance then official genbit.'
& $taskPython20 -B -u (Join-Path $taskBuild20 'resume_io_verify20.py') `
    1> (Join-Path $taskBuild20 'resume_io_verify20.stdout.log') `
    2> (Join-Path $taskBuild20 'resume_io_verify20.stderr.log')
$taskBuildCode20 = $LASTEXITCODE
Get-Content (Join-Path $taskBuild20 'resume_io_verify20.stdout.log') -Tail 10
Get-Content (Join-Path $taskBuild20 'resume_io_verify20.stderr.log') -Tail 10
if ($taskBuildCode20 -ne 0) { throw "verify20 exited $taskBuildCode20" }
if (-not (Test-Path (Join-Path $taskBuild20 'BIT_MANIFEST.json'))) {
    throw 'verify20 produced no qualified bit; no programming'
}
Write-Output 'New qualified bit generated. Running full check, SRAM program and real camera captures.'
& $taskPython20 -B -u (Join-Path $PSScriptRoot 'runner.py') `
    1> (Join-Path $PSScriptRoot 'execution.stdout.log') `
    2> (Join-Path $PSScriptRoot 'execution.stderr.log')
$taskDeliveryCode20 = $LASTEXITCODE
Get-Content (Join-Path $PSScriptRoot 'execution.stdout.log') -Tail 12
Get-Content (Join-Path $PSScriptRoot 'execution.stderr.log') -Tail 12
exit $taskDeliveryCode20
