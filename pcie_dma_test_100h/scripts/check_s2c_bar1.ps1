param(
    [switch]$SkipPrepare,
    [string]$StageIdfPath
)

# Guard the S2-C promotion boundary without editing generated IP files.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

function Require-Pattern {
    param([string]$Text, [string]$Pattern, [string]$Description)
    if ($Text -notmatch $Pattern) { $Failures.Add("Missing $Description") }
}

$IdfPath = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.idf'
$WrapperPath = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.v'
$DocPath = Join-Path $ProjectRoot 'doc\S2C_BAR1_REGENERATION.md'
$StagingScriptPath = Join-Path $PSScriptRoot 'regenerate_bar1_staging.ps1'
if ([string]::IsNullOrWhiteSpace($StageIdfPath)) {
    $StageIdfPath = Join-Path $ProjectRoot 'build\ipgen\pcie_bar1\pcie_test.idf'
}
foreach ($Path in @($IdfPath, $WrapperPath, $DocPath, $StagingScriptPath)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Failures.Add("Required S2-C BAR1 file not found: $Path")
    }
}

if ($Failures.Count -eq 0) {
    $Idf = Get-Content -Raw -Encoding UTF8 -LiteralPath $IdfPath
    $Wrapper = Get-Content -Raw -Encoding UTF8 -LiteralPath $WrapperPath
    $Doc = Get-Content -Raw -Encoding UTF8 -LiteralPath $DocPath
    Require-Pattern $Idf '(?s)<name>BAR1_Enable</name>\s*<value>false</value>' 'disabled BAR1 IDF fact'
    Require-Pattern $Wrapper 'BAR1_ENABLED\s*=\s*1''b0' 'disabled BAR1 wrapper fact'
    Require-Pattern $Wrapper 'BAR1_MASK\s*=\s*31''h0' 'zero BAR1 wrapper mask'
    Require-Pattern $Doc 'pcie_test\.v.*BAR1_ENABLED.*BAR1_MASK' 'generated-file edit prohibition'
    Require-Pattern $Doc '0x110..0x113' 'DMA command-window coverage'
    Require-Pattern $Doc '5432_1000' 'canonical DMA data contract'
}

if ($Failures.Count -eq 0 -and -not $SkipPrepare) {
    $IdfHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $IdfPath).Hash
    $WrapperHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $WrapperPath).Hash
    & $StagingScriptPath
    if (-not (Test-Path -LiteralPath $StageIdfPath -PathType Leaf)) {
        $Failures.Add("BAR1 staging IDF was not created: $StageIdfPath")
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $IdfPath).Hash -cne $IdfHashBefore) {
        $Failures.Add('BAR1 dry run modified the canonical IDF')
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $WrapperPath).Hash -cne $WrapperHashBefore) {
        $Failures.Add('BAR1 dry run modified the canonical wrapper')
    }
}

if ($Failures.Count -eq 0) {
    try {
        $StageText = Get-Content -Raw -Encoding UTF8 -LiteralPath $StageIdfPath
        $StageXml = [xml]$StageText
    } catch {
        $Failures.Add("BAR1 staging IDF is not valid XML: $($_.Exception.Message)")
    }
}

if ($Failures.Count -eq 0) {
    foreach ($ExpectedParam in @(
        @{ Name = 'BAR1_Enable'; Value = 'true' },
        @{ Name = 'BAR1_Size'; Value = '512' },
        @{ Name = 'BAR1_Size_Unit'; Value = 'Bytes' },
        @{ Name = 'BAR1_MASK_EN'; Value = 'false' },
        @{ Name = 'BAR1_MASK'; Value = "31'h0" }
    )) {
        $Nodes = $StageXml.SelectNodes("//param[name='$($ExpectedParam.Name)']/value")
        if ($Nodes.Count -ne 1) {
            $Failures.Add("Expected one staging $($ExpectedParam.Name) value, found $($Nodes.Count)")
        } elseif ($Nodes[0].InnerText -cne $ExpectedParam.Value) {
            $Failures.Add("Unexpected staging $($ExpectedParam.Name) value '$($Nodes[0].InnerText)'")
        }
    }

    $NormalizedStage = [regex]::Replace(
        $StageText,
        '(?s)(<name>BAR1_Size</name>\s*.*?<value>)512(</value>)',
        '${1}256${2}'
    )
    $NormalizedStage = [regex]::Replace(
        $NormalizedStage,
        '(?s)(<name>BAR1_Enable</name>\s*<value>)true(</value>)',
        '${1}false${2}'
    )
    if ($NormalizedStage -cne $Idf) {
        $Failures.Add('BAR1 staging IDF contains changes beyond Enable=false->true and Size=256->512')
    }
}

if ($Failures.Count -gt 0) {
    throw "S2-C BAR1 gate failed:`n - $($Failures -join "`n - ")"
}

Write-Host 'INFO: S2-C BAR1 boundary and staging gate passed; canonical BAR1 remains intentionally disabled'
