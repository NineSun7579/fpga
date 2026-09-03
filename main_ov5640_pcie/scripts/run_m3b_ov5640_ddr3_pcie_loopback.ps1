param([string]$SimulatorExecPath = $env:QUESTA_BIN)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($SimulatorExecPath)) { throw 'SimulatorExecPath or QUESTA_BIN is required' }
$RunId = [guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $ProjectRoot (Join-Path 'build' (Join-Path 'm3b-ov5640-ddr3-pcie-loopback' $RunId))
$WorkLib = Join-Path $RunRoot 'work'
$LogPath = Join-Path $RunRoot 'run.log'
$Vlib = Join-Path $SimulatorExecPath 'vlib.exe'
$Vlog = Join-Path $SimulatorExecPath 'vlog.exe'
$Vmap = Join-Path $SimulatorExecPath 'vmap.exe'
$Vsim = Join-Path $SimulatorExecPath 'vsim.exe'
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
Push-Location $RunRoot
try {
    & $Vlib $WorkLib 2>&1 | Tee-Object $LogPath
    if ($LASTEXITCODE -ne 0) { throw "vlib.exe failed with exit code $LASTEXITCODE" }
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
        (Join-Path $ProjectRoot 'rtl\rgb565_axis4_mwr_descriptor.sv'),
        (Join-Path $ProjectRoot 'rtl\rgb565_axis4_pcie_mwr_bridge.sv'),
        (Join-Path $ProjectRoot 'rtl\rgb565_axis4_pcie_mwr_path.sv'),
        (Join-Path $ProjectRoot 'tb\tb_ov5640_ddr3_pcie_loopback.sv')
    )
    & $Vlog -sv -work $WorkLib $Sources 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw "vlog.exe failed with exit code $LASTEXITCODE" }
    & $Vmap work $WorkLib 2>&1 | Tee-Object $LogPath -Append
    if ($LASTEXITCODE -ne 0) { throw "vmap.exe failed with exit code $LASTEXITCODE" }
    & $Vsim -c -lib work tb_ov5640_ddr3_pcie_loopback -do 'run -all; quit -f' 2>&1 | Tee-Object $LogPath -Append
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
    Write-Output "M3-B OV5640 DDR3 PCIe loopback PASS: $LogPath"
} finally {
    Pop-Location
}
