param(
    [switch]$AllowKnownBaselineIssues
)

# Validate the reproducible implementation evidence. Strict mode is the
# release-facing default; the explicit baseline switch only reproduces the
# historical vendor example and never declares it release-ready.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$PdsRoot = Join-Path $BuildRoot 'pds'
$BuildLog = Join-Path $BuildRoot 'logs\pds-gen_bit_stream.log'
$TimingReport = Join-Path $PdsRoot 'report_timing\test_ddr.rtr'

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
    'Synthesis netlist' = Join-Path $PdsRoot 'synthesize\test_ddr_syn.vm'
    'Post-PNR simulation netlist' = Join-Path $PdsRoot 'generate_netlist\test_ddr_sim.v'
    'Slow-corner SDF' = Join-Path $PdsRoot 'generate_netlist\test_ddr_sta.sdf'
    'PDS bitstream' = Join-Path $PdsRoot 'generate_bitstream\test_ddr.sbit'
    'Binary bitstream' = Join-Path $PdsRoot 'generate_bitstream\test_ddr.bin'
}

foreach ($Artifact in $RequiredArtifacts.GetEnumerator()) {
    Assert-NonEmptyFile -Path $Artifact.Value -Description $Artifact.Key
}

$BuildText = Get-Content -Raw -LiteralPath $BuildLog
$FatalPatterns = [ordered]@{
    'PDS error record' = '(?m)^E:'
    'License checkout failure' = '(?im)License checkout failed'
    'Device mismatch' = '(?m)^W:\s+Flow-4058:'
}

foreach ($Fatal in $FatalPatterns.GetEnumerator()) {
    if ($BuildText -match $Fatal.Value) {
        throw "Build log contains $($Fatal.Key): $BuildLog"
    }
}

$RequiredLogPatterns = [ordered]@{
    'Synthesis completed' = "Design 'test_ddr' has been successfully synthesized to architecture-specific objects\."
    'Mapping completed' = "Design 'test_ddr' has been successfully mapped to architecture-specific objects\."
    'PNR completed' = "Design 'test_ddr' has been placed and routed successfully\."
    'Timing completed' = 'Report timing is finished successfully\.'
    'Netlist completed' = 'Generate Netlist is finished successfully\.'
    'Bitstream completed' = 'Generating Programming File done\.'
    'Script completed' = 'INFO: DDR3 bring-up implementation completed'
}

foreach ($Stage in $RequiredLogPatterns.GetEnumerator()) {
    if ($BuildText -notmatch $Stage.Value) {
        throw "Required stage marker missing: $($Stage.Key)"
    }
}

$TimingText = Get-Content -Raw -LiteralPath $TimingReport
if ($TimingText -notmatch '(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$') {
    throw 'Final timing report does not contain All Constraints Met.'
}
if ($TimingText -match 'Some Constraints Violated') {
    throw 'Final timing report contains constraint violations.'
}
if ($TimingText -notmatch '(?m)^\| Device\s+: PG2L100H\s*$' -or
    $TimingText -notmatch '(?m)^\| Speed Grade\s+: -6\s*$' -or
    $TimingText -notmatch '(?m)^\| Package\s+: FBG484\s*$') {
    throw 'Final timing report does not match PG2L100H-6IFBG484.'
}

$TimingRows = foreach ($Line in Get-Content -LiteralPath $TimingReport) {
    if ($Line -match '^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$') {
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
            FailingEndpoints = [int]$Matches[5]
            TotalEndpoints = [int]$Matches[6]
        }
    }
}

if (-not $TimingRows) {
    throw 'No timing summary rows were parsed from the final report.'
}

$RequiredClocks = @(
    'ref_clk',
    'rst_clk',
    'ddrphy_sysclk',
    'phy_dq_sysclk_0',
    'phy_dq_sysclk_1'
)
foreach ($Clock in $RequiredClocks) {
    $ClockRows = $TimingRows | Where-Object {
        $_.LaunchClock -eq $Clock -or $_.CaptureClock -eq $Clock
    }
    if (-not $ClockRows) {
        throw "Expected timing clock is missing from summary rows: $Clock"
    }
}

$FailedRows = $TimingRows | Where-Object {
    $_.Slack -lt 0 -or
    $_.TotalNegativeSlack -ne 0 -or
    $_.FailingEndpoints -ne 0
}
if ($FailedRows) {
    $Details = $FailedRows | Format-Table -AutoSize | Out-String
    throw "Timing summary contains failing rows:`n$Details"
}

$KnownIssuePatterns = [ordered]@{
    'BIST error-data width mismatch' =
        '(?m)^W:\s+Verilog-2019:.*Width mismatch between port err_data_(?:pre|aft).*axi_bist_top_v1_0'
    'BIST error-data cleanup' =
        '(?m)^W:\s+Public-4008:.*u_test_(?:rd|wr)_ctrl/err_data_(?:pre|aft).*dangling and will be cleaned'
    'Reset uses share pin' =
        '(?m)^C:\s+ConstraintEditor-2002:.*Port rst_board.*share pin\.'
    'Incompatible bank VCCIO' =
        '(?m)^C:\s+Place-2025:\s+The VCCIO .* is incompatible\.'
    'UART I/O constraint missing' =
        "(?m)^W:\s+ConstraintEditor-4019:\s+Port 'uart_(?:rxd|txd)' unspecified I/O constraint\."
    'Top-level input timing missing' =
        "(?m)^W:\s+Timing-4086:\s+Port '.*' is not constrained"
    'Top-level output timing missing' =
        "(?m)^W:\s+Timing-4087:\s+Port '.*' is not constrained"
    'SCBV not configured' =
        '(?m)^W:\s+Bitstream-2001:\s+SCBV has not been set'
}

$DetectedIssues = foreach ($Issue in $KnownIssuePatterns.GetEnumerator()) {
    $IssueMatches = [regex]::Matches($BuildText, $Issue.Value)
    if ($IssueMatches.Count -gt 0) {
        Write-Warning "$($Issue.Key): $($IssueMatches.Count) occurrence(s)"
        $Issue.Key
    }
}

$KnownCriticalPatterns = @(
    $KnownIssuePatterns['Reset uses share pin'],
    $KnownIssuePatterns['Incompatible bank VCCIO']
)
$UnknownCriticalLines = foreach ($Line in Get-Content -LiteralPath $BuildLog) {
    if ($Line -notmatch '^C:') {
        continue
    }

    $IsKnown = $false
    foreach ($Pattern in $KnownCriticalPatterns) {
        if ($Line -match $Pattern) {
            $IsKnown = $true
            break
        }
    }
    if (-not $IsKnown) {
        $Line
    }
}
if ($UnknownCriticalLines) {
    throw "Build log contains unclassified critical warnings:`n$($UnknownCriticalLines -join "`n")"
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

Write-Host 'INFO: DDR3 build artifact checks completed'
