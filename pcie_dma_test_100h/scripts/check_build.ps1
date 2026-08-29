param(
    [switch]$AllowKnownBaselineIssues
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$PdsRoot = Join-Path $BuildRoot 'pds'
$BuildLog = Join-Path $BuildRoot 'logs\pds-gen_bit_stream.log'
$TimingReport = Join-Path $PdsRoot 'report_timing\pcie_dma_test.rtr'

function Assert-NonEmptyFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }

    $File = Get-Item -LiteralPath $Path
    if ($File.Length -le 0) {
        throw "$Description is empty: $Path"
    }
}

Assert-NonEmptyFile -Path $BuildLog -Description 'PDS build log'
Assert-NonEmptyFile -Path $TimingReport -Description 'Final timing report'

$RequiredArtifacts = [ordered]@{
    'Post-PNR simulation netlist' = Join-Path $PdsRoot 'generate_netlist\pcie_dma_test_sim.v'
    'Slow-corner SDF' = Join-Path $PdsRoot 'generate_netlist\pcie_dma_test_sta.sdf'
    'PDS bitstream' = Join-Path $PdsRoot 'generate_bitstream\pcie_dma_test.sbit'
    'Binary bitstream' = Join-Path $PdsRoot 'generate_bitstream\pcie_dma_test.bin'
}

foreach ($Artifact in $RequiredArtifacts.GetEnumerator()) {
    Assert-NonEmptyFile -Path $Artifact.Value -Description $Artifact.Key
}

if (Select-String -LiteralPath $BuildLog -Pattern '^E:' -Quiet) {
    throw "PDS log contains one or more error records: $BuildLog"
}

$TimingText = Get-Content -Raw -LiteralPath $TimingReport
if ($TimingText -notmatch 'Design Summary\s*:\s*All Constraints Met\.') {
    throw 'Final timing report does not contain All Constraints Met.'
}
if ($TimingText -match 'Some Constraints Violated') {
    throw 'Final timing report contains constraint violations.'
}

$TimingRows = foreach ($Line in Get-Content -LiteralPath $TimingReport) {
    if ($Line -match '^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+\d+\s+\d+\s*$') {
        [pscustomobject]@{
            LaunchClock = $Matches[1]
            CaptureClock = $Matches[2]
            Slack = [double]::Parse(
                $Matches[3],
                [Globalization.CultureInfo]::InvariantCulture
            )
            TotalNegativeSlack = [double]::Parse(
                $Matches[4],
                [Globalization.CultureInfo]::InvariantCulture
            )
        }
    }
}

if (-not $TimingRows) {
    throw 'No timing summary rows were parsed from the final report.'
}

$FailedRows = $TimingRows | Where-Object {
    $_.Slack -lt 0 -or $_.TotalNegativeSlack -ne 0
}
if ($FailedRows) {
    $Details = $FailedRows | Format-Table -AutoSize | Out-String
    throw "Timing summary contains negative slack:`n$Details"
}

$KnownIssuePatterns = [ordered]@{
    'PCIe IP device mismatch' = 'Flow-4058:.*device information PG2L50H'
    'UART RX tied low' = 'Verilog-2036:.*Net rxd connected.*has no driver'
    'Unconstrained top-level I/O' = 'Timing-408[67]: Port .* is not constrained'
    'Unspecified PCIe serial I/O constraints' = 'ConstraintEditor-4019: Port Bus'
    'Share-pin placement requires board review' = 'ConstraintEditor-2002:.*share pin'
    'SCBV not configured' = 'Bitstream-2001: SCBV has not been set'
}

$DetectedIssues = foreach ($Issue in $KnownIssuePatterns.GetEnumerator()) {
    $IssueMatches = Select-String `
        -LiteralPath $BuildLog `
        -Pattern $Issue.Value

    if ($IssueMatches) {
        Write-Warning "$($Issue.Key): $($IssueMatches.Count) occurrence(s)"
        $Issue.Key
    }
}

$WorstSlack = ($TimingRows | Measure-Object -Property Slack -Minimum).Minimum
Write-Host "INFO: timing gate passed; worst parsed slack is $WorstSlack ns"
foreach ($Artifact in $RequiredArtifacts.GetEnumerator()) {
    $Size = (Get-Item -LiteralPath $Artifact.Value).Length
    Write-Host "INFO: $($Artifact.Key): $Size bytes"
}

if ($DetectedIssues -and -not $AllowKnownBaselineIssues) {
    throw "Strict build gate failed: $($DetectedIssues -join '; ')"
}

if ($DetectedIssues) {
    Write-Warning 'Known baseline issues were explicitly allowed; this build is not release-ready.'
}

Write-Host 'INFO: PCIe build artifact checks completed'
