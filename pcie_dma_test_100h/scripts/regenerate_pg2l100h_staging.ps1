param(
    [switch]$Execute,
    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin'
)

# Generate a PG2L100H PCIe candidate under build/ only; canonical IP is untouched.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceIdf = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.idf'
$StageRoot = Join-Path $ProjectRoot 'build\ipgen\pcie_pg2l100h'
$StageIdf = Join-Path $StageRoot 'pcie_test.idf'
$Generator = Join-Path $PdsBin 'ip_generate.exe'
$InstallIndex = Get-ChildItem -LiteralPath (Join-Path $PdsBin '..\ip') -Recurse -File -Filter 'index.xml' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '(?i)pcie' } |
    Select-Object -First 1

if (-not (Test-Path -LiteralPath $SourceIdf -PathType Leaf)) {
    throw "Active PCIe IDF not found: $SourceIdf"
}
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
$Text = Get-Content -Raw -Encoding UTF8 -LiteralPath $SourceIdf
$Text = $Text -replace '<device>PG2L50H</device>', '<device>PG2L100H</device>'
[IO.File]::WriteAllText($StageIdf, $Text, [Text.UTF8Encoding]::new($false))

Write-Host "INFO: prepared PG2L100H PCIe staging IDF at $StageIdf"
Write-Host 'INFO: target Logos2 / PG2L100H / FBG484 / -6; canonical IP was not modified'
if (-not $Execute) {
    Write-Host 'INFO: dry run only; pass -Execute to invoke ip_generate.exe'
    return
}
if (-not (Test-Path -LiteralPath $Generator -PathType Leaf)) {
    throw "PDS IP generator not found: $Generator"
}
if ($null -eq $InstallIndex) {
    throw 'PDS PCIe instance index.xml is not installed; install the Logos2 PCI Express IP package before generation'
}
Copy-Item -LiteralPath $InstallIndex.FullName -Destination (Join-Path $StageRoot 'index.xml') -Force

& $Generator -i $StageIdf -m $StageRoot -family Logos2 -device PG2L100H -pack FBG484 -speed -6 -log (Join-Path $StageRoot 'generate.log')
if ($LASTEXITCODE -ne 0) {
    throw "PDS PG2L100H PCIe staging generation failed with exit code $LASTEXITCODE; inspect $StageRoot\generate.log"
}
Write-Host 'INFO: PG2L100H PCIe staging generation completed; canonical IP was not modified'
