param(
    [ValidateSet(
        'compile',
        'synthesize',
        'dev_map',
        'pnr',
        'report_timing',
        'gen_netlist',
        'gen_bit_stream'
    )]
    [string]$RunTo = 'compile',

    [switch]$AllowKnownBaselineIssues
)

# Strict mode is release-facing. The baseline switch only proves that the
# current design can be reproduced; it never declares the result release-ready.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$PdsRoot = Join-Path $BuildRoot 'pds'
$BuildLog = Join-Path $BuildRoot "logs\pds-$RunTo.log"
$TimingReport = Join-Path $PdsRoot 'report_timing\ov7725_hdmi.rtr'

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

$StageOrder = @(
    'compile',
    'synthesize',
    'dev_map',
    'pnr',
    'report_timing',
    'gen_netlist',
    'gen_bit_stream'
)
$FinalStageIndex = [Array]::IndexOf($StageOrder, $RunTo)

Assert-NonEmptyFile -Path $BuildLog -Description 'PDS build log'
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

if ($BuildText -notmatch
    '(?m)^Executing : set_arch -family Logos2 -device PG2L100H -package FBG484 -speedgrade -6 successfully\.\s*$') {
    throw 'Build log does not match Logos2/PG2L100H/FBG484/-6.'
}
if ($BuildText -notmatch '(?m)^INFO: top module: ov7725_hdmi\s*$') {
    throw 'Build log does not identify ov7725_hdmi as the top module.'
}

$ExpectedSources = @(
    'rtl/ov7725_hdmi.v',
    'rtl/ov7725_dri/i2c_dri.v',
    'rtl/ov7725_dri/i2c_ov7725_rgb565_cfg.v',
    'rtl/ov7725_dri/ov7725_dri.v',
    'rtl/hdmi_top/asyn_rst_syn.v',
    'rtl/hdmi_top/dvi_encoder.v',
    'rtl/hdmi_top/dvi_transmitter_top.v',
    'rtl/hdmi_top/hdmi_top.v',
    'rtl/hdmi_top/serializer_10_to_1.v',
    'rtl/hdmi_top/video_driver.v',
    'rtl/ddr3_ctrl_top/aq_axi_master.v',
    'rtl/ddr3_ctrl_top/ctrl_fifo.v',
    'rtl/ddr3_ctrl_top/ddr3_ctrl_top.v',
    'rtl/ddr3_ctrl_top/ddr3_rw_ctrl.v',
    'rtl/ov7725_dri/cmos_capture_data.v',
    'rtl/hdmi_top/video_display.v',
    'prj/ipcore/pll_clk/pll_clk.idf',
    'prj/ipcore/ddr3_ip/ddr3_ip.idf',
    'prj/ipcore/wr_fifo/wr_fifo.idf',
    'prj/ipcore/rd_fifo/rd_fifo.idf'
)
foreach ($RelativePath in $ExpectedSources) {
    $SourcePattern = '(?m)^Executing : add_design .*/' +
        [regex]::Escape($RelativePath) + ' successfully\.\s*$'
    if ($BuildText -notmatch $SourcePattern) {
        throw "Expected design input is missing from the build log: $RelativePath"
    }
}

$DesignInputCount = [regex]::Matches(
    $BuildText,
    '(?m)^Executing : add_design .* successfully\.\s*$'
).Count
if ($DesignInputCount -ne $ExpectedSources.Count) {
    throw "Expected 20 design inputs, found $DesignInputCount."
}

$ConstraintPattern =
    '(?m)^Executing : add_constraint .*/prj/source/ov7725_hdmi\.fdc successfully\.\s*$'
if ($BuildText -notmatch $ConstraintPattern) {
    throw 'The active OV7725 FDC is missing from the build log.'
}
$ConstraintCount = [regex]::Matches(
    $BuildText,
    '(?m)^Executing : add_constraint .* successfully\.\s*$'
).Count
if ($ConstraintCount -ne 1) {
    throw "Expected one constraint input, found $ConstraintCount."
}

$RequiredLogPatterns = [ordered]@{
    'compile' = 'Process "Compile" done\.'
    'synthesize' = "Design 'ov7725_hdmi' has been successfully synthesized to architecture-specific objects\."
    'dev_map' = "Design 'ov7725_hdmi' has been successfully mapped to architecture-specific objects\."
    'pnr' = "Design 'ov7725_hdmi' has been placed and routed successfully\."
    'report_timing' = 'Report timing is finished successfully\.'
    'gen_netlist' = 'Generate Netlist is finished successfully\.'
    'gen_bit_stream' = 'Generating Programming File done\.'
}
for ($Index = 0; $Index -le $FinalStageIndex; $Index++) {
    $Stage = $StageOrder[$Index]
    if ($BuildText -notmatch $RequiredLogPatterns[$Stage]) {
        throw "Required stage marker missing: $Stage"
    }
}

$ExpectedScriptMarker = if ($RunTo -eq 'gen_bit_stream') {
    'INFO: OV7725 HDMI implementation completed'
} else {
    "INFO: requested stage $RunTo completed"
}
if ($BuildText -notmatch [regex]::Escape($ExpectedScriptMarker)) {
    throw "Build script completion marker missing: $ExpectedScriptMarker"
}

$RequiredArtifacts = [ordered]@{}
if ($FinalStageIndex -ge [Array]::IndexOf($StageOrder, 'synthesize')) {
    $RequiredArtifacts['Synthesis netlist'] =
        Join-Path $PdsRoot 'synthesize\ov7725_hdmi_syn.vm'
}
if ($FinalStageIndex -ge [Array]::IndexOf($StageOrder, 'gen_netlist')) {
    $RequiredArtifacts['Post-PNR simulation netlist'] =
        Join-Path $PdsRoot 'generate_netlist\ov7725_hdmi_sim.v'
    $RequiredArtifacts['Slow-corner SDF'] =
        Join-Path $PdsRoot 'generate_netlist\ov7725_hdmi_sta.sdf'
}
if ($FinalStageIndex -ge [Array]::IndexOf($StageOrder, 'gen_bit_stream')) {
    $RequiredArtifacts['PDS bitstream'] =
        Join-Path $PdsRoot 'generate_bitstream\ov7725_hdmi.sbit'
    $RequiredArtifacts['Binary bitstream'] =
        Join-Path $PdsRoot 'generate_bitstream\ov7725_hdmi.bin'
}
foreach ($Artifact in $RequiredArtifacts.GetEnumerator()) {
    Assert-NonEmptyFile -Path $Artifact.Value -Description $Artifact.Key
}

$KnownIssuePatterns = [ordered]@{
    'Hand-written RTL width mismatch' =
        '(?m)^W:\s+Verilog-2019:.*[\\/]41_ov7725_hdmi[\\/]rtl[\\/].*Width mismatch between port'
}

$FailedTimingRows = @()
if ($FinalStageIndex -ge [Array]::IndexOf($StageOrder, 'report_timing')) {
    Assert-NonEmptyFile -Path $TimingReport -Description 'Final timing report'
    $TimingText = Get-Content -Raw -LiteralPath $TimingReport

    if ($TimingText -notmatch '(?m)^\| Device\s+: PG2L100H\s*$' -or
        $TimingText -notmatch '(?m)^\| Speed Grade\s+: -6\s*$' -or
        $TimingText -notmatch '(?m)^\| Package\s+: FBG484\s*$') {
        throw 'Final timing report does not match PG2L100H-6FBG484.'
    }

    $TimingSummaryLines = Get-Content -LiteralPath $TimingReport |
        Select-Object -First 253
    $TimingRows = foreach ($Line in $TimingSummaryLines) {
        if ($Line -match
            '^\s*(?:\S+\s+){0,2}(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$') {
            [pscustomobject]@{
                Slack = [double]::Parse(
                    $Matches[1],
                    [Globalization.CultureInfo]::InvariantCulture
                )
                TotalNegativeSlack = [double]::Parse(
                    $Matches[2],
                    [Globalization.CultureInfo]::InvariantCulture
                )
                FailingEndpoints = [int]$Matches[3]
                TotalEndpoints = [int]$Matches[4]
            }
        }
    }
    if (-not $TimingRows) {
        throw 'No timing summary rows were parsed from the final report.'
    }

    $FailedTimingRows = @($TimingRows | Where-Object {
        $_.Slack -lt 0 -or
        $_.TotalNegativeSlack -ne 0 -or
        $_.FailingEndpoints -ne 0
    })
    if ($FailedTimingRows) {
        if ($TimingText -notmatch
            '(?m)^Design Summary\s*:\s*Some Constraints Violated\.\s*$') {
            throw 'Timing rows fail but the design summary does not report violations.'
        }
    } elseif ($TimingText -notmatch
        '(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$') {
        throw 'Final timing report has no recognized design summary.'
    }

    if ($AllowKnownBaselineIssues -and $FailedTimingRows) {
        $ActualEndpointSets = @($FailedTimingRows |
            ForEach-Object { "$($_.FailingEndpoints)/$($_.TotalEndpoints)" } |
            Sort-Object)
        $ExpectedEndpointSets = @(
            '11/11',
            '11/11',
            '20/20',
            '20/20',
            '53/53',
            '53/53'
        )
        if (($ActualEndpointSets -join ',') -ne
            ($ExpectedEndpointSets -join ',')) {
            throw "Baseline timing failures changed: $($ActualEndpointSets -join ', ')"
        }
    }

    $KnownIssuePatterns['Clock pins without timing propagation'] =
        '(?m)^W:\s+STA-3011:'
    $KnownIssuePatterns['Clock sources without constraints'] =
        '(?m)^C:\s+SDC-2025:'
    $KnownIssuePatterns['Sub-optimal clock routing'] =
        '(?m)^C:\s+Route-2036:'
    $KnownIssuePatterns['Clock topology requires review'] =
        '(?m)^C:\s+DeviceMap-2011:'
    $KnownIssuePatterns['Clock placement requires review'] =
        '(?m)^C:\s+Place-2028:'
    $KnownIssuePatterns['Share-pin placement requires board review'] =
        '(?m)^C:\s+ConstraintEditor-2002:.*share pin\.'
    $KnownIssuePatterns['Top-level input timing missing'] =
        "(?m)^W:\s+Timing-4086:\s+Port '.*' is not constrained"
    $KnownIssuePatterns['Top-level output timing missing'] =
        "(?m)^W:\s+Timing-4087:\s+Port '.*' is not constrained"
    $KnownIssuePatterns['SCBV not configured'] =
        '(?m)^W:\s+Bitstream-2001:\s+SCBV has not been set'
}

$DetectedIssues = @()
if ($FailedTimingRows) {
    Write-Warning "Final timing constraints violated: $($FailedTimingRows.Count) summary row(s)"
    $DetectedIssues += 'Final timing constraints violated'
}
foreach ($Issue in $KnownIssuePatterns.GetEnumerator()) {
    $IssueMatches = [regex]::Matches($BuildText, $Issue.Value)
    if ($IssueMatches.Count -gt 0) {
        Write-Warning "$($Issue.Key): $($IssueMatches.Count) occurrence(s)"
        $DetectedIssues += $Issue.Key
    }
}

$KnownCriticalPatterns = @(
    '(?m)^C:\s+SDC-2025:',
    '(?m)^C:\s+Route-2036:',
    '(?m)^C:\s+DeviceMap-2011:',
    '(?m)^C:\s+Place-2028:',
    '(?m)^C:\s+ConstraintEditor-2002:.*share pin\.'
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

Write-Host "INFO: OV7725 build checks completed through stage '$RunTo'"
