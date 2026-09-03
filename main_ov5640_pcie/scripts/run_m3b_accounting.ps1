[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$SimulatorExecPath)
$ErrorActionPreference = 'Stop'; $Root = Split-Path -Parent $PSScriptRoot
$Id = Get-Date -Format 'yyyyMMdd-HHmmss'; $Run = Join-Path $Root (Join-Path 'build' (Join-Path 'm3b-accounting' $Id)); $Work = Join-Path $Run 'work'; $Log = Join-Path $Run 'run.log'
function E { param([string]$N); $P = Join-Path $SimulatorExecPath $N; if (!(Test-Path -LiteralPath $P -PathType Leaf)) { throw "Missing executable: $P" }; $P }
New-Item -ItemType Directory -Force -Path $Run | Out-Null; $Vlib=E vlib.exe; $Vlog=E vlog.exe; $Vmap=E vmap.exe; $Vsim=E vsim.exe
Push-Location $Run; try { & $Vlib $Work 2>&1 | Tee-Object $Log; if($LASTEXITCODE){throw 'vlib failed'}; & $Vlog -sv -work $Work (Join-Path $Root 'rtl\rgb565_axis4_frame_accounting.sv') (Join-Path $Root 'tb\tb_rgb565_axis4_frame_accounting.sv') 2>&1 | Tee-Object $Log -Append; if($LASTEXITCODE){throw 'vlog failed'}; & $Vmap work $Work 2>&1 | Tee-Object $Log -Append; if($LASTEXITCODE){throw 'vmap failed'}; & $Vsim -c -lib work tb_rgb565_axis4_frame_accounting -do 'run -all; quit -f' 2>&1 | Tee-Object $Log -Append; if($LASTEXITCODE){exit $LASTEXITCODE}; if(@(Select-String -LiteralPath $Log -Pattern '^(?:# )?TEST PASS$').Count -ne 1){throw 'TEST PASS count mismatch'}; "M3-B accounting PASS: $Log" } finally { Pop-Location }
