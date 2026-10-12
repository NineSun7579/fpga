$phaseRoot = $PSScriptRoot
$Host.UI.RawUI.WindowTitle = 'build04 mapping60_01 REAL LOG'
$offsets = @{}
while ($true) {
    foreach ($name in @('controller.log','mapping.log','mapping_export.log')) {
        $targetLog = Join-Path $phaseRoot $name
        if (Test-Path $targetLog) {
            $lines = @(Get-Content -LiteralPath $targetLog)
            $offset = 0
            if ($offsets.ContainsKey($name)) { $offset = $offsets[$name] }
            if ($lines.Count -gt $offset) {
                Write-Host ('[' + $name + ']') -ForegroundColor Cyan
                $lines[$offset..($lines.Count - 1)] | ForEach-Object { Write-Host $_ }
                $offsets[$name] = $lines.Count
            }
        }
    }
    if (Test-Path (Join-Path $phaseRoot 'final_result.json')) {
        Get-Content (Join-Path $phaseRoot 'final_result.json')
        break
    }
    Start-Sleep -Seconds 2
}
