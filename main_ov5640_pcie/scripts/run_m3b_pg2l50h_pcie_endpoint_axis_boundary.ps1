[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$SimulatorExecPath)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepositoryRoot = Split-Path -Parent $ProjectRoot
$RunId = [guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $ProjectRoot (Join-Path 'build' (Join-Path 'm3b-pg2l50h-pcie-endpoint-axis-boundary' $RunId))
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
$VendorRoot = Join-Path $RepositoryRoot 'pcie_dma_test_100h\hdl\pcie_dma_ctrl'
$Sources = @(
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_pcie_tx_request_arbiter.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_pcie_tx_cdc_arbiter.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_pcie_tx_top_adapter.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_tx_top.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_tx_cpld_rd_ctrl.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_tx_mwr_rd_ctrl.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_cpld_tx_ctrl.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_mrd_tx_ctrl.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_mwr_tx_ctrl.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_rd_ctrl.v'),
    (Join-Path $VendorRoot 'ips2l_pcie_dma_tlp_tx_mux.v'),
    (Join-Path $VendorRoot 'pgs_pciex4_prefetch_fifo_v1_2.v'),
    (Join-Path $VendorRoot 'fifo\pgs_pciex4_fifo_v1_2.v'),
    (Join-Path $VendorRoot 'fifo\pgs_pciex4_fifo_ctrl.v'),
    (Join-Path $VendorRoot 'fifo\ipm_distributed_sdpram_v1_2_distributed_fifo.v'),
    (Join-Path $ProjectRoot 'tb\tb_rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv')
)

Push-Location $RunRoot
try {
    & $Vlib $WorkLib 2>&1 | Tee-Object $LogPath
    if ($LASTEXITCODE -ne 0) { throw 'vlib.exe failed' }
    & $Vlog -sv -work $WorkLib $Sources 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw 'vlog.exe failed' }
    & $Vmap work $WorkLib 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw 'vmap.exe failed' }
    & $Vsim -c -lib work tb_rgb565_pg2l50h_pcie_endpoint_axis_boundary `
        -do 'run -all; quit -f' 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (@(Select-String -LiteralPath $LogPath -Pattern '^(?:# )?TEST PASS$').Count -ne 1) {
        throw 'Expected exactly one TEST PASS marker'
    }
    if (@(Select-String -LiteralPath $LogPath -Pattern 'Errors: 0').Count -ne 2) {
        throw 'Expected zero errors in both compile and simulation summaries'
    }
    if (@(Select-String -LiteralPath $LogPath -Pattern 'Warnings: 0').Count -ne 2) {
        throw 'Expected zero warnings in both compile and simulation summaries'
    }
    Write-Output "M3-B PCIe Endpoint AXIS boundary PASS: $LogPath"
}
finally {
    Pop-Location
}
