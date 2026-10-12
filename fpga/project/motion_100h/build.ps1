param([switch]$Check, [string]$Resume = '')
$ErrorActionPreference = 'Stop'
$python = 'C:\Users\NineSun\anaconda3\python.exe'
$runner = Join-Path $PSScriptRoot 'build.py'
if ($Check) {
    & $python $runner --check
} elseif ($Resume) {
    & $python $runner --run --resume $Resume
} else {
    & $python $runner --run
}
if ($LASTEXITCODE -ne 0) { throw "Isolated motion build failed (exit $LASTEXITCODE); see status.json and run logs" }
