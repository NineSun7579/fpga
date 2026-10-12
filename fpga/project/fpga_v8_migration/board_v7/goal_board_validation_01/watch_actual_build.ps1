$Host.UI.RawUI.WindowTitle = 'FPGA actual logs: mapping probes -> IO bank -> candidate'
$boardRoot = Split-Path $PSScriptRoot -Parent
$roots = @(
    (Join-Path $boardRoot 'source_diagnostics_timing_build_01/route_attempt_03'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map02/evidence'),
    (Join-Path $boardRoot 'source_diagnostics_timing_build_03/evidence'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map03/execution'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map04'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map05'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map06'),
    (Join-Path $boardRoot 'diagnostic_io_bank_report01')
)
$states = @(
    (Join-Path $boardRoot 'diagnostic_sync_register_map02/evidence/final_result.json'),
    (Join-Path $boardRoot 'source_diagnostics_timing_build_03/evidence/runtime/controller_status.json'),
    (Join-Path $boardRoot 'source_diagnostics_timing_build_03/evidence/runtime/actual_result.json'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map03/evidence/actual_final_result.json'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map04/evidence/actual_final_result.json'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map05/evidence/actual_final_result.json'),
    (Join-Path $boardRoot 'diagnostic_sync_register_map06/evidence/actual_final_result.json')
)
$seen = @{}
Write-Host 'Read-only actual logs. Missing results remain PENDING. Ctrl+C closes this monitor.'
while ($true) {
    $probeRoots = @(Get-ChildItem -LiteralPath $boardRoot -Directory -Filter 'diagnostic_sync_register_map*' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $bankRoots = @(Get-ChildItem -LiteralPath $boardRoot -Directory -Filter 'diagnostic_io_bank_report*' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $candidateRoots = @(Get-ChildItem -LiteralPath $boardRoot -Directory -Filter 'source_diagnostics_timing_build_*' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $activeRoots = @($roots + $probeRoots + $bankRoots + $candidateRoots | Sort-Object -Unique)
    $probeStates = @($probeRoots | ForEach-Object { Join-Path $_ 'evidence/actual_final_result.json' })
    $activeStates = @($states + $probeStates | Sort-Object -Unique)
    foreach ($state in $activeStates) {
        if (Test-Path -LiteralPath $state) {
            $text = Get-Content -LiteralPath $state -Raw -ErrorAction SilentlyContinue
            # Queue timestamps change every few seconds. Show semantic phase changes.
            try {
                $doc = $text | ConvertFrom-Json
                $key = "$($doc.phase)|$($doc.status)|$($doc.gate.status)|$($doc.gate.reason)"
            } catch { $key = $text }
            if ($seen[$state] -ne $key) {
                Write-Host "`n[$(Get-Date -Format o)] $state" -ForegroundColor Cyan
                Write-Host $text
                $seen[$state] = $key
            }
        }
    }
    foreach ($root in $activeRoots) {
        $latest = Get-ChildItem -LiteralPath $root -Filter '*.log' -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
        if ($latest) {
            $key = "$($latest.Length)|$($latest.LastWriteTimeUtc.Ticks)"
            if ($seen[$latest.FullName] -ne $key) {
                Write-Host "`n[$(Get-Date -Format o)] $($latest.FullName)" -ForegroundColor Green
                Get-Content -LiteralPath $latest.FullName -Tail 12 -ErrorAction SilentlyContinue
                $seen[$latest.FullName] = $key
            }
        }
    }
    Start-Sleep -Seconds 5
}
