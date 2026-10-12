$taskRoot = $PSScriptRoot
$Host.UI.RawUI.WindowTitle = 'build04_functional_route04 REAL PNR'
while ($true) {
    Clear-Host
    Write-Host 'build04_functional_route04 - latest real tool log'
    $controllerLog = Get-ChildItem $taskRoot -Filter 'controller*.stdout.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($controllerLog) { Get-Content $controllerLog.FullName -Tail 12 }
    $taskLog = Get-ChildItem $taskRoot -Filter '*.log' | Where-Object { $_.Name -notmatch 'controller' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($taskLog) { Write-Host $taskLog.FullName; Get-Content $taskLog.FullName -Tail 24 }
    Start-Sleep -Seconds 3
}
