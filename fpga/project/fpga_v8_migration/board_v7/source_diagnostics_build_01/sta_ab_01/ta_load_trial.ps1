param([Parameter(Mandatory=$true)][string]$Out)
$ErrorActionPreference='Stop'
& "$PSScriptRoot/ta_activate.ps1"
& "$PSScriptRoot/ta_click.ps1"
Start-Sleep -Milliseconds 800
& "$PSScriptRoot/ta_import.ps1" -Out $Out
