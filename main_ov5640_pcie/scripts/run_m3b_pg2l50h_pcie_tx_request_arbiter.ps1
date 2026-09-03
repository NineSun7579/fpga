[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$SimulatorExecPath)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunId = [guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $ProjectRoot (Join-Path 'build' (Join-Path 'm3b-pg2l50h-tx-arbiter' $RunId))
$WorkLib = Join-Path $RunRoot 'work'
$LogPath = Join-Path $RunRoot 'run.log'

function Require-Executable {
    param([string]$Name)
    $Path = Join-Path $SimulatorExecPath $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required simulator executable not found: $Path"
    }
    return $Path
}

New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$Vlib = Require-Executable 'vlib.exe'
$Vlog = Require-Executable 'vlog.exe'
$Vmap = Require-Executable 'vmap.exe'
$Vsim = Require-Executable 'vsim.exe'
$Sources = @(
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_pcie_tx_request_arbiter.sv'),
    (Join-Path $ProjectRoot 'tb\tb_rgb565_pg2l50h_pcie_tx_request_arbiter.sv')
)

Push-Location $RunRoot
try {
    & $Vlib $WorkLib 2>&1 | Tee-Object $LogPath
    if ($LASTEXITCODE -ne 0) { throw 'vlib.exe failed' }
    & $Vlog -sv -work $WorkLib $Sources 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw 'vlog.exe failed' }
    & $Vmap work $WorkLib 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw 'vmap.exe failed' }
    & $Vsim -c -lib work tb_rgb565_pg2l50h_pcie_tx_request_arbiter `
        -do 'run -all; quit -f' 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (@(Select-String -LiteralPath $LogPath -Pattern '^(?:# )?TEST PASS$').Count -ne 1) {
        throw 'Expected exactly one TEST PASS marker'
    }
    if (@(Select-String -LiteralPath $LogPath -Pattern 'Errors: 0').Count -lt 1) {
        throw 'Expected Errors: 0 in Questa summary'
    }
    if (@(Select-String -LiteralPath $LogPath -Pattern 'Warnings: 0').Count -lt 1) {
        throw 'Expected Warnings: 0 in Questa summary'
    }
    Write-Output "M3-B PG2L50H PCIe TX request arbiter PASS: $LogPath"
}
finally {
    Pop-Location
}
