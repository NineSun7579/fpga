param(
    [string]$RepoRoot
)

# Verify that project-owned Questa sources stay inside each project archive.
# This structural check does not run PDS or Questa.
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)

    $Failures.Add($Message)
}

$Archives = @(
    [pscustomobject]@{
        Name = 'DDR3'
        Path = 'ddr3_test/ddr3_test/sim/questa'
    },
    [pscustomobject]@{
        Name = 'PCIe DMA'
        Path = 'pcie_dma_test_100h/sim/questa'
    },
    [pscustomobject]@{
        Name = 'camera HDMI'
        Path = '41_ov7725_hdmi/sim/questa'
    }
)

foreach ($Archive in $Archives) {
    $ArchivePath = Join-Path $RepoRoot ($Archive.Path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $ArchivePath -PathType Container)) {
        Add-Failure "$($Archive.Name) Questa archive not found: $ArchivePath"
        continue
    }

    $ReadmePath = Join-Path $ArchivePath 'README.md'
    if (-not (Test-Path -LiteralPath $ReadmePath -PathType Leaf)) {
        Add-Failure "$($Archive.Name) Questa archive README not found: $ReadmePath"
    }

    $RuntimeDirectories = @(Get-ChildItem -LiteralPath $ArchivePath -Recurse -Directory |
        Where-Object { $_.Name -ieq 'work' -or $_.Name -ieq 'build' })
    foreach ($Directory in $RuntimeDirectories) {
        Add-Failure "$($Archive.Name) archive contains runtime directory: $($Directory.FullName)"
    }

    $RuntimeFiles = @(Get-ChildItem -LiteralPath $ArchivePath -Recurse -File |
        Where-Object {
            $_.Name -in @('modelsim.ini', 'transcript') -or
            $_.Extension -in @('.mpf', '.wlf', '.vcd', '.ucdb', '.log')
        })
    foreach ($File in $RuntimeFiles) {
        Add-Failure "$($Archive.Name) archive contains runtime file: $($File.FullName)"
    }

    Write-Host "INFO: checked $($Archive.Name) Questa archive"
}

$PcieArchive = Join-Path $RepoRoot 'pcie_dma_test_100h\sim\questa'
$RequiredPcieSources = @(
    'tb\pcie_test_smoke_model.sv',
    'tb\tb_pcie_dma_test.sv',
    'tb\tb_pcie_dma_link.sv',
    'tb\tb_pcie_dma_s2c.sv',
    'tb\tb_pcie_dma_post_syn.sv',
    'tb\tb_pcie_dma_post_pnr_func.sv'
)
foreach ($RelativePath in $RequiredPcieSources) {
    $SourcePath = Join-Path $PcieArchive $RelativePath
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        Add-Failure "PCIe archived simulation source not found: $SourcePath"
    }
}

$LegacyPcieTbPath = Join-Path $RepoRoot 'pcie_dma_test_100h\tb'
if (Test-Path -LiteralPath $LegacyPcieTbPath) {
    $LegacySources = @(Get-ChildItem -LiteralPath $LegacyPcieTbPath -File |
        Where-Object { $_.Extension -in @('.v', '.sv', '.vh', '.svh') })
    foreach ($Source in $LegacySources) {
        Add-Failure "PCIe simulation source remains outside sim/questa: $($Source.FullName)"
    }
}

if ($Failures.Count -gt 0) {
    Write-Error ("Simulation archive gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: simulation archive gate passed'
exit 0
