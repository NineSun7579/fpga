param()

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
foreach ($Path in @($IdfPath, $WrapperPath, $DocPath)) {
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
    Require-Pattern $Doc '禁止只手改' 'generated-file edit prohibition'
    Require-Pattern $Doc '0x110..0x113' 'DMA command-window coverage'
    Require-Pattern $Doc '5432_1000' 'canonical DMA data contract'
}

if ($Failures.Count -gt 0) {
    throw "S2-C BAR1 gate failed:`n - $($Failures -join "`n - ")"
}

Write-Host 'INFO: S2-C BAR1 regeneration boundary gate passed; BAR1 remains intentionally disabled'
