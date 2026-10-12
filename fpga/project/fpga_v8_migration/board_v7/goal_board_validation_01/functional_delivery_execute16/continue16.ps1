$ErrorActionPreference = 'Stop'
$taskRoot16 = Split-Path $PSScriptRoot -Parent
$taskBuild16 = Join-Path (Split-Path $taskRoot16 -Parent) 'build04_functional_route04'
$taskPython16 = 'C:\Users\NineSun\anaconda3\python.exe'
$taskStart16 = Join-Path $PSScriptRoot 'serial_corrected_started.json'
if (Test-Path $taskStart16) { throw 'Never repeat serial continuation16' }
$taskProcesses16 = @()
foreach ($taskWait16 in @(
    @{Id=44000; Pattern='build04_functional_route04.*resume_hold_limit15.py'},
    @{Id=85996; Pattern='functional_delivery_execute15.*runner.py'}
)) {
    $taskProcess16 = Get-CimInstance Win32_Process -Filter "ProcessId=$($taskWait16.Id)"
    if ($null -ne $taskProcess16) {
        if ($taskProcess16.CommandLine -notmatch $taskWait16.Pattern) {
            throw "Previous process identity changed: $($taskWait16.Id)"
        }
        $taskProcesses16 += $taskProcess16 | Select-Object ProcessId,CreationDate,Name,CommandLine
    }
}
@{utc=[DateTime]::UtcNow.ToString('o'); processes=$taskProcesses16; goal_complete=$false} |
    ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $taskStart16
foreach ($taskProcess16 in $taskProcesses16) {
    Wait-Process -Id $taskProcess16.ProcessId -ErrorAction SilentlyContinue
}
if (Test-Path (Join-Path $taskBuild16 'BIT_MANIFEST.json')) {
    throw 'Previous build produced a qualified bit; review its delivery instead of rebuilding'
}
if (-not (Test-Path (Join-Path $taskBuild16 'HOLD_LIMIT15_FAIL.json'))) {
    throw 'Previous hold attempt has no complete native timing failure receipt'
}
Write-Host 'Previous attempt exited. Continuing default placement and native hold repair.'
& $taskPython16 -B -u (Join-Path $taskBuild16 'resume_default_hold16.py') `
    1> (Join-Path $taskBuild16 'resume_default_hold16.stdout.log') `
    2> (Join-Path $taskBuild16 'resume_default_hold16.stderr.log')
$taskBuildCode16 = $LASTEXITCODE
Get-Content (Join-Path $taskBuild16 'resume_default_hold16.stderr.log') -Tail 12
if ($taskBuildCode16 -ne 0) { throw "Recovery16 exited $taskBuildCode16" }
if (-not (Test-Path (Join-Path $taskBuild16 'BIT_MANIFEST.json'))) {
    throw 'Recovery16 has no qualified bit; no programming'
}
Write-Host 'New candidate generated. Checking delivery, SRAM programming and real camera captures.'
& $taskPython16 -B -u (Join-Path $PSScriptRoot 'runner.py') `
    1> (Join-Path $PSScriptRoot 'execution.stdout.log') `
    2> (Join-Path $PSScriptRoot 'execution.stderr.log')
$taskDeliveryCode16 = $LASTEXITCODE
Get-Content (Join-Path $PSScriptRoot 'execution.stdout.log') -Tail 12
Get-Content (Join-Path $PSScriptRoot 'execution.stderr.log') -Tail 12
exit $taskDeliveryCode16
