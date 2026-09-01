param(
    [switch]$Execute,
    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin'
)

# Prepare a BAR1-enabled IDF in build/ only. Canonical generated IP is untouched.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceIdf = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.idf'
$StageRoot = Join-Path $ProjectRoot 'build\ipgen\pcie_bar1'
$StageIdf = Join-Path $StageRoot 'pcie_test.idf'
$Generator = Join-Path $PdsBin 'ip_generate.exe'

if (-not (Test-Path -LiteralPath $SourceIdf -PathType Leaf)) {
    throw "Active PCIe IDF not found: $SourceIdf"
}
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
$Text = Get-Content -Raw -Encoding UTF8 -LiteralPath $SourceIdf
$Text = $Text -replace '(?s)(<name>BAR1_Size</name>\s*.*?<value>)256(</value>)', '${1}512${2}'
$Text = $Text -replace '(?s)(<name>BAR1_Enable</name>\s*<value>)false(</value>)', '${1}true${2}'
$Text = $Text -replace '(?s)(<name>BAR1_MASK</name>\s*<value>)31''h0(</value>)', '${1}31''h0(</value>)'
[IO.File]::WriteAllText($StageIdf, $Text, [Text.UTF8Encoding]::new($false))

Write-Host "INFO: prepared BAR1 staging IDF at $StageIdf"
Write-Host 'INFO: target Logos2 / PG2L50H / FBG484 / -6; BAR1 size 512 Bytes'
if (-not $Execute) {
    Write-Host 'INFO: dry run only; pass -Execute to invoke ip_generate.exe'
    exit 0
}
if (-not (Test-Path -LiteralPath $Generator -PathType Leaf)) {
    throw "PDS IP generator not found: $Generator"
}

& $Generator -i $StageIdf -m $StageRoot -family Logos2 -device PG2L50H -pack FBG484 -speed -6 -log (Join-Path $StageRoot 'generate.log')
if ($LASTEXITCODE -ne 0) {
    throw "PDS IP generation failed with exit code $LASTEXITCODE"
}
Write-Host 'INFO: BAR1 staging generation completed; canonical IP was not modified'
