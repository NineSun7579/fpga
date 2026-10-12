$Host.UI.RawUI.WindowTitle = 'build04 diagnostic PNR / functional export - live log'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
while ($true) {
    foreach ($stage in @('help','pnr','functional','graph')) {
        $path = Join-Path $root ($stage + '.log')
        if (Test-Path $path) {
            $lines = Get-Content $path -Tail 14
            Write-Host ('--- ' + $stage + ' ' + (Get-Date))
            $lines | Write-Host
        }
    }
    if (Test-Path (Join-Path $root 'export_result.json')) { Write-Host 'Export finished; evidence preserved'; Read-Host 'Press Enter to close'; break }
    if (Test-Path (Join-Path $root 'failure.json')) { Write-Host 'Diagnostic blocked; failure evidence preserved'; Read-Host 'Press Enter to close'; break }
    Start-Sleep -Seconds 5
    Clear-Host
}
