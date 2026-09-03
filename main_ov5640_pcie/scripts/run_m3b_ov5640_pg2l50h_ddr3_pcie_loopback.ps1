[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$SimulatorExecPath)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepositoryRoot = Split-Path -Parent $ProjectRoot
$RunId = [guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $ProjectRoot (Join-Path 'build' (Join-Path 'm3b-ov5640-pg2l50h-ddr3-pcie' $RunId))
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
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_capture.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_grayscale.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_pipeline.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_word_packer.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_word_pipeline.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_word_skid_buffer.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_word_to_axis4_adapter.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_async_fifo.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_cdc_bridge.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_cdc_staging_pipeline.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_ddr3_write_descriptor.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_frame_commit.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_frame_slot_table.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_frame_read_scheduler.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_frame_readout_gate.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_mwr_descriptor.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_pcie_mwr_bridge.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_pcie_mwr_path.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_axis4_committed_pcie_mwr_path.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_ddr3_pcie_pipeline.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_ddr3_write_adapter.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_pg2l50h_ddr3_read_adapter.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_pg2l50h_pcie_pipeline.sv'),
    (Join-Path $RepositoryRoot 'pcie_dma_test_100h\hdl\pcie_dma_ctrl\ips2l_pcie_dma_mwr_tx_ctrl.v'),
    (Join-Path $ProjectRoot 'tb\tb_ov5640_pg2l50h_ddr3_pcie_loopback.sv')
)

Push-Location $RunRoot
try {
    & $Vlib $WorkLib 2>&1 | Tee-Object $LogPath
    if ($LASTEXITCODE -ne 0) { throw 'vlib.exe failed' }
    & $Vlog -sv -work $WorkLib $Sources 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw 'vlog.exe failed' }
    & $Vmap work $WorkLib 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw 'vmap.exe failed' }
    & $Vsim -c -lib work tb_ov5640_pg2l50h_ddr3_pcie_loopback `
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
    Write-Output "M3-B OV5640 canonical DDR3 PCIe loopback PASS: $LogPath"
}
finally {
    Pop-Location
}
