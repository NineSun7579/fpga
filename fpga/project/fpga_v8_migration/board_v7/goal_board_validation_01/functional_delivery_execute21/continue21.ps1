$ErrorActionPreference = 'Stop'
$taskRoot21 = Split-Path $PSScriptRoot -Parent
$taskBuild21 = Join-Path (Split-Path $taskRoot21 -Parent) 'build04_functional_route04'
$taskPython21 = 'C:\Users\NineSun\anaconda3\python.exe'
$taskStart21 = Join-Path $PSScriptRoot 'serial_started.json'
if (Test-Path $taskStart21) { throw 'Never repeat serial continuation21' }
$taskBusy21 = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(pds|pds_shell|pnr|ta)\.exe$' -or
    ($_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'resume_genbit_final21.py|functional_delivery_execute21.*runner.py') })
if ($taskBusy21.Count -gt 0) { throw 'Vendor or continuation21 process still busy' }
@{utc=[DateTime]::UtcNow.ToString('o'); goal_complete=$false} | ConvertTo-Json | Set-Content -Encoding UTF8 $taskStart21
Write-Output 'Verifying the genbit-final routed database with complete native acceptance.'
& $taskPython21 -B -u (Join-Path $taskBuild21 'resume_genbit_final21.py') `
    1> (Join-Path $taskBuild21 'resume_genbit_final21.stdout.log') `
    2> (Join-Path $taskBuild21 'resume_genbit_final21.stderr.log')
$taskBuildCode21 = $LASTEXITCODE
Get-Content (Join-Path $taskBuild21 'resume_genbit_final21.stdout.log') -Tail 10
Get-Content (Join-Path $taskBuild21 'resume_genbit_final21.stderr.log') -Tail 10
if ($taskBuildCode21 -ne 0) { throw "resume21 exited $taskBuildCode21" }
if (-not (Test-Path (Join-Path $taskBuild21 'BIT_MANIFEST.json'))) {
    throw 'resume21 produced no qualified bit; no programming'
}
Write-Output 'Qualified. Running full check, SRAM program and real camera captures.'
& $taskPython21 -B -u (Join-Path $PSScriptRoot 'runner.py') `
    1> (Join-Path $PSScriptRoot 'execution.stdout.log') `
    2> (Join-Path $PSScriptRoot 'execution.stderr.log')
$taskDeliveryCode21 = $LASTEXITCODE
Get-Content (Join-Path $PSScriptRoot 'execution.stdout.log') -Tail 12
Get-Content (Join-Path $PSScriptRoot 'execution.stderr.log') -Tail 12
exit $taskDeliveryCode21
