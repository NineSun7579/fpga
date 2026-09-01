param()

# Validate the S2-C fixed DMA write/readback contract without running Questa.
# Dynamic TLP transport and completion data remain authoritative only after
# the simulator run passes.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)

    $Failures.Add($Message)
}

function Require-File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-Failure "$Description not found: $Path"
        return $false
    }

    Write-Host "INFO: found $Description"
    return $true
}

function Require-Pattern {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][string]$Description
    )

    if (-not [regex]::IsMatch($Text, $Pattern)) {
        Add-Failure "Missing $Description"
    }
}

function Get-FileListEntries {
    param([Parameter(Mandatory)][string]$Path)

    return @(Get-Content -LiteralPath $Path |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') -and -not $_.StartsWith('//') })
}

$FileListPath = Join-Path $ProjectRoot 'sim\questa\dma.f'
$RunDoPath = Join-Path $ProjectRoot 'sim\questa\run_dma.do'
$TestbenchPath = Join-Path $ProjectRoot 'sim\questa\tb\tb_pcie_dma_s2c.sv'
$RunPath = Join-Path $PSScriptRoot 'run.ps1'

$RequiredFiles = [ordered]@{
    $FileListPath = 'PCIe S2-C filelist'
    $RunDoPath = 'PCIe S2-C simulation DO'
    $TestbenchPath = 'PCIe S2-C archived testbench'
    $RunPath = 'PCIe PowerShell entry'
}

$AllFilesExist = $true
foreach ($Entry in $RequiredFiles.GetEnumerator()) {
    if (-not (Require-File -Path $Entry.Key -Description $Entry.Value)) {
        $AllFilesExist = $false
    }
}
if (-not $AllFilesExist) {
    throw "PCIe S2-C static gate failed:`n - $($Failures -join "`n - ")"
}

$ExpectedFileListEntries = @(
    '+define+IPS2L_PCIE_SPEEDUP_SIM',
    '+define+IPM_HSST_SPEEDUP_SIM',
    '+define+DWC_DISABLE_CDC_METHOD_REPORTING',
    '+incdir+hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl',
    '+incdir+ipcore/pcie_test/sim/modelsim',
    '-f sim/questa/link_vendor_local.f',
    '-f scripts/pds_sources.f',
    'sim/questa/tb/tb_pcie_dma_s2c.sv'
)
$FileListEntries = @(Get-FileListEntries -Path $FileListPath)
if ((Compare-Object $ExpectedFileListEntries $FileListEntries -SyncWindow 0).Count -gt 0) {
    Add-Failure 'PCIe S2-C filelist does not match the approved ordered contract'
}
foreach ($Entry in $FileListEntries) {
    if ($Entry -match '^[A-Za-z]:[/\\]' -or $Entry.Contains('\')) {
        Add-Failure "PCIe S2-C filelist entry is not POSIX project-relative: $Entry"
    }
}

$TestbenchText = Get-Content -Raw -Encoding UTF8 -LiteralPath $TestbenchPath
$RunDoText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunDoPath
$RunText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunPath

foreach ($Required in ([ordered]@{
        'S2-C testbench module' = '(?m)^module\s+tb_pcie_dma_s2c\s*;'
        'vendor Root Complex' = '\bpango_pcie_top_sim\s*#\s*\('
        'project Endpoint' = '\bpcie_dma_test\s+u_dut\s*\('
        'fixed DMA address' = "DMA_ADDRESS\s*=\s*32'h0000_2000"
        'fixed one-DW length' = "DMA_LENGTH_MINUS_ONE\s*=\s*10'h000"
        'fixed DMA data' = "DMA_DATA\s*=\s*32'hA5C3_5A3C"
        'configuration-space BAR write' = 'configure_endpoint_bar0'
        'real RC DMA write' = 'rc_dma_write_one_dw'
        'real RC DMA read' = 'rc_dma_read_one_dw'
        'completion arrival wait' = 'wait_for_read_completion'
        'full returned-data comparison' = 'readback_data\s*!==\s*DMA_DATA'
        'write reception comparison' = 'written_data\s*!==\s*DMA_DATA'
        'link stability prerequisite' = 'wait_for_real_link'
        'bounded watchdog' = '#8ms\s*;\s*\r?\n\s*\$fatal'
        'S2-C success marker' = '\$display\("INFO: S2C_DMA_WRITE_READBACK_OK"\)'
        'unique PASS source' = '\$display\("TEST PASS"\)'
        'simulation hierarchy warning' = '(?s)depends on named internal status and DMA.*?nets'
    }).GetEnumerator()) {
    Require-Pattern -Text $TestbenchText -Pattern $Required.Value -Description $Required.Key
}
if ([regex]::Matches($TestbenchText, '\$display\("TEST PASS"\)').Count -ne 1 -or
    [regex]::Matches($TestbenchText, '\$display\("INFO: S2C_DMA_WRITE_READBACK_OK"\)').Count -ne 1) {
    Add-Failure 'PCIe S2-C testbench must contain one success marker and one TEST PASS source'
}

foreach ($Required in ([ordered]@{
        'DO fail-fast handler' = 'onerror\s*\{'
        'DO project-root requirement' = 'info exists env\(SIM_PROJECT_ROOT\)'
        'DO run identity' = 'SIM_RUN_ID'
        'DO run-scoped work library' = 'build/sim/dma/\$env\(SIM_RUN_ID\)'
        'DO separate vendor library' = 'vmap\s+pcie_vendor\s+\$vendor_dir'
        'DO vendor compiler call' = 'do\s+sim/questa/compile_vendor_link\.do'
        'DO S2-C filelist compile' = 'vlog\s+-sv\s+-override_timescale\s+1ns/10ps\s+-work\s+work\s+-f\s+sim/questa/dma\.f'
        'DO S2-C elaboration' = 'work\.tb_pcie_dma_s2c'
        'DO bounded completion' = 'run\s+-all'
    }).GetEnumerator()) {
    Require-Pattern -Text $RunDoText -Pattern $Required.Value -Description $Required.Key
}
if ($RunDoText -match '[A-Za-z]:[/\\]') {
    Add-Failure 'PCIe S2-C DO contains an absolute Windows path'
}

foreach ($Required in ([ordered]@{
        'PowerShell S2-C action' = "'sim-dma'"
        'PowerShell S2-C DO binding' = "-DoFileName 'sim/questa/run_dma\.do'"
        'PowerShell S2-C log binding' = "-LogFileName 'sim-dma\.log'"
        'PowerShell S2-C success marker' = "-SuccessMarker 'INFO: S2C_DMA_WRITE_READBACK_OK'"
    }).GetEnumerator()) {
    Require-Pattern -Text $RunText -Pattern $Required.Value -Description $Required.Key
}

if ($Failures.Count -gt 0) {
    throw "PCIe S2-C static gate failed:`n - $($Failures -join "`n - ")"
}

Write-Host 'INFO: PCIe S2-C static simulation gate passed; dynamic DMA was not executed'
