param([switch]$Check)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\NineSun\anaconda3\python.exe'
if ($Check) { & $python "$here\build.py" --check; exit $LASTEXITCODE }
& $python -u "$here\build.py" --run
if ($LASTEXITCODE -ne 0) { throw '100H build failed; inspect private run logs/status' }
