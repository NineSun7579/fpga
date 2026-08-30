param(
    [switch]$AllowKnownBaselineIssues
)

# Strict mode is release-facing. Baseline mode only reproduces one exact
# reviewed failure fingerprint and never permits device metadata drift.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$PdsRoot = Join-Path $BuildRoot 'pds'
$BuildLog = Join-Path $BuildRoot 'logs\pds-gen_bit_stream.log'
$TimingReport = Join-Path $PdsRoot 'report_timing\pcie_dma_test.rtr'
$IpDefinition = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.idf'
$BitstreamDatabase = Join-Path $PdsRoot 'generate_bitstream\bgr.db'
$BaselineFingerprintPath = Join-Path $ProjectRoot `
    'doc\H2B_BASELINE_FINGERPRINT.json'

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
Assert-NonEmptyFile -Path $IpDefinition -Description 'PCIe IP definition'
Assert-NonEmptyFile -Path $BitstreamDatabase -Description 'Bitstream database'
Assert-NonEmptyFile `
    -Path $BaselineFingerprintPath `
    -Description 'PCIe H2-B0 baseline fingerprint'

$MetadataIssues = [System.Collections.Generic.List[string]]::new()
try {
    [xml]$IpXml = Get-Content -Raw -Encoding UTF8 -LiteralPath $IpDefinition
} catch {
    throw "PCIe IP definition is not valid XML: $IpDefinition"
}

$ExpectedMetadata = [ordered]@{
    family = 'Logos2'
    device = 'PG2L50H'
    package = 'FBG484'
    speedgrade = '-6'
}
foreach ($Field in $ExpectedMetadata.GetEnumerator()) {
    $ActualValue = [string]$IpXml.ip_inst.header.($Field.Key)
    if ($ActualValue -ne $Field.Value) {
        $Message = "PCIe IP metadata $($Field.Key) is '$ActualValue'; expected '$($Field.Value)'"
        $MetadataIssues.Add($Message)
        Write-Warning $Message
    }
}
if ($MetadataIssues.Count -gt 0) {
    throw "PCIe IP metadata gate failed: $($MetadataIssues -join '; ')"
}

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
if ($TimingText -notmatch '(?im)\bDevice\s*:\s*PG2L50H\b') {
    throw 'Final timing report does not identify device PG2L50H.'
}
if ($TimingText -notmatch 'Design Summary\s*:\s*All Constraints Met\.') {
    throw 'Final timing report does not contain All Constraints Met.'
}
if ($TimingText -match 'Some Constraints Violated') {
    throw 'Final timing report contains constraint violations.'
}

$BuildText = Get-Content -Raw -LiteralPath $BuildLog
if ($BuildText -notmatch '(?im)-device\s+PG2L50H') {
    throw 'PDS build log does not record set_arch device PG2L50H.'
}
if ($BuildText -match '(?im)PG2L100H') {
    throw 'PDS build log contains stale PG2L100H device metadata.'
}

$BitstreamText = Get-Content -Raw -LiteralPath $BitstreamDatabase
if ($BitstreamText -notmatch '(?im)PG2L50H-6FBG484') {
    throw 'Bitstream database does not identify PG2L50H-6FBG484.'
}
if ($BitstreamText -match '(?im)PG2L100H') {
    throw 'Bitstream database contains stale PG2L100H device metadata.'
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

function Get-BaselineIssueSignatureCounts {
    param([AllowEmptyString()][string[]]$Lines)

    $Counts = [Collections.Generic.Dictionary[string, int]]::new(
        [StringComparer]::Ordinal
    )

    foreach ($Line in $Lines) {
        $Signature = $null

        if ($Line -match
            '^W:\s+Verilog-2036:.*\bNet (\S+) connected to input port of module instance (\S+) has no driver, tie it to 0\s*$') {
            $Signature = "Verilog-2036|$($Matches[1])|$($Matches[2])"
        } elseif ($Line -match
            "^W:\s+(Timing-408[67]):\s+Port '([^']+)' is not constrained") {
            $Signature = "$($Matches[1])|$($Matches[2])"
        } elseif ($Line -match
            "^W:\s+ConstraintEditor-4019:\s+Port Bus '([^']+)' unspecified I/O constraint") {
            $Signature = "ConstraintEditor-4019|$($Matches[1])"
        } elseif ($Line -match
            '^C:\s+ConstraintEditor-2002:.*\|\s+Port (\S+) has been placed at location (\S+), whose type is share pin\.\s*$') {
            $Signature = "ConstraintEditor-2002|$($Matches[1])|$($Matches[2])"
        } elseif ($Line -match
            '^C:\s+Bitstream-2001:\s+SCBV has not been set\.') {
            $Signature = 'Bitstream-2001|SCBV'
        } elseif ($Line -match
            '^[WC]:\s+(Verilog-2036|Timing-408[67]|ConstraintEditor-(?:4019|2002)|Bitstream-2001):') {
            # Preserve an unrecognized monitored-code line as a new signature
            # so baseline mode cannot silently ignore a changed message shape.
            $Signature = "$($Matches[1])|UNPARSED|$Line"
        }

        if ($null -eq $Signature) {
            continue
        }
        if ($Counts.ContainsKey($Signature)) {
            $Counts[$Signature]++
        } else {
            $Counts.Add($Signature, 1)
        }
    }

    return ,$Counts
}

try {
    $Fingerprint = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $BaselineFingerprintPath |
        ConvertFrom-Json
} catch {
    throw "PCIe H2-B0 baseline fingerprint is not valid JSON: $BaselineFingerprintPath"
}
if ($Fingerprint.schema_version -ne 1) {
    throw "Unsupported PCIe H2-B0 fingerprint schema: $($Fingerprint.schema_version)"
}
foreach ($Field in $ExpectedMetadata.GetEnumerator()) {
    $FingerprintValue = [string]$Fingerprint.approved_target.($Field.Key)
    if ($FingerprintValue -ne $Field.Value) {
        throw "PCIe H2-B0 fingerprint target $($Field.Key) is '$FingerprintValue'; expected '$($Field.Value)'"
    }
}

$ExpectedIssueCounts = [Collections.Generic.Dictionary[string, int]]::new(
    [StringComparer]::Ordinal
)
foreach ($Entry in @($Fingerprint.signatures)) {
    $Signature = [string]$Entry.signature
    $Occurrences = [int]$Entry.occurrences
    if ([string]::IsNullOrWhiteSpace($Signature) -or $Occurrences -le 0) {
        throw 'PCIe H2-B0 fingerprint contains an empty signature or non-positive count.'
    }
    if ($ExpectedIssueCounts.ContainsKey($Signature)) {
        throw "PCIe H2-B0 fingerprint contains duplicate signature: $Signature"
    }
    $ExpectedIssueCounts.Add($Signature, $Occurrences)
}

$ExpectedRawOccurrences = (
    $ExpectedIssueCounts.Values | Measure-Object -Sum
).Sum
if ($ExpectedIssueCounts.Count -ne [int]$Fingerprint.expected_unique_signatures -or
    $ExpectedRawOccurrences -ne [int]$Fingerprint.expected_raw_occurrences) {
    throw 'PCIe H2-B0 fingerprint summary does not match its signature entries.'
}

$ActualIssueCounts = Get-BaselineIssueSignatureCounts `
    -Lines (Get-Content -LiteralPath $BuildLog)

$IssueGroups = [ordered]@{
    'UART RX tied low' = '^Verilog-2036\|'
    'Unconstrained top-level I/O' = '^Timing-408[67]\|'
    'Unspecified PCIe serial I/O constraints' = '^ConstraintEditor-4019\|'
    'Share-pin placement requires board review' = '^ConstraintEditor-2002\|'
    'SCBV not configured' = '^Bitstream-2001\|'
}
$DetectedIssues = foreach ($Issue in $IssueGroups.GetEnumerator()) {
    $MatchingSignatures = @($ActualIssueCounts.Keys | Where-Object {
            $_ -match $Issue.Value
        })
    if ($MatchingSignatures.Count -eq 0) {
        continue
    }
    $OccurrenceCount = 0
    foreach ($Signature in $MatchingSignatures) {
        $OccurrenceCount += $ActualIssueCounts[$Signature]
    }
    Write-Warning ("{0}: {1} signature(s), {2} occurrence(s)" -f `
            $Issue.Key, $MatchingSignatures.Count, $OccurrenceCount)
    $Issue.Key
}

if ($AllowKnownBaselineIssues) {
    $AllSignatures = @(
        @($ExpectedIssueCounts.Keys) + @($ActualIssueCounts.Keys) |
            Sort-Object -CaseSensitive -Unique
    )
    $FingerprintDifferences = [Collections.Generic.List[string]]::new()
    foreach ($Signature in $AllSignatures) {
        $ExpectedCount = if ($ExpectedIssueCounts.ContainsKey($Signature)) {
            $ExpectedIssueCounts[$Signature]
        } else {
            0
        }
        $ActualCount = if ($ActualIssueCounts.ContainsKey($Signature)) {
            $ActualIssueCounts[$Signature]
        } else {
            0
        }
        if ($ExpectedCount -ne $ActualCount) {
            $FingerprintDifferences.Add(
                "$Signature expected=$ExpectedCount actual=$ActualCount"
            )
        }
    }
    if ($FingerprintDifferences.Count -gt 0) {
        throw ("PCIe H2-B0 baseline fingerprint changed:`n- {0}" -f `
                ($FingerprintDifferences -join "`n- "))
    }
    Write-Host ("INFO: PCIe H2-B0 baseline fingerprint matched {0} signatures and {1} occurrences" -f `
            $ActualIssueCounts.Count, $ExpectedRawOccurrences)
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
