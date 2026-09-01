param(
    [switch]$Execute,
    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin'
)

# Prepare a BAR1-enabled IDF in build/ only. Canonical generated IP is untouched.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceIdf = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.idf'
$SourceIndex = Join-Path $ProjectRoot 'ipcore\pcie_test\index.xml'
$StageRoot = Join-Path $ProjectRoot 'build\ipgen\pcie_bar1'
$StageIdf = Join-Path $StageRoot 'pcie_test.idf'
$Generator = Join-Path $PdsBin 'ip_generate.exe'

function Replace-UniqueText {
    param(
        [Parameter(Mandatory)] [string]$InputText,
        [Parameter(Mandatory)] [string]$Pattern,
        [Parameter(Mandatory)] [string]$Replacement,
        [Parameter(Mandatory)] [string]$Description
    )

    $Found = [regex]::Matches($InputText, $Pattern)
    if ($Found.Count -ne 1) {
        throw "Expected exactly one $Description in the active IDF, found $($Found.Count)"
    }
    return [regex]::Replace($InputText, $Pattern, $Replacement)
}

function Require-UniqueParamValue {
    param(
        [Parameter(Mandatory)] [xml]$Document,
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Expected
    )

    $Nodes = $Document.SelectNodes("//param[name='$Name']/value")
    if ($Nodes.Count -ne 1) {
        throw "Expected exactly one $Name value in the staging IDF, found $($Nodes.Count)"
    }
    if ($Nodes[0].InnerText -cne $Expected) {
        throw "Unexpected staging value for ${Name}: '$($Nodes[0].InnerText)', expected '$Expected'"
    }
}

if (-not (Test-Path -LiteralPath $SourceIdf -PathType Leaf)) {
    throw "Active PCIe IDF not found: $SourceIdf"
}
if ($Execute -and -not (Test-Path -LiteralPath $SourceIndex -PathType Leaf)) {
    throw "PDS IP generation requires instance metadata index.xml beside the active IDF: $SourceIndex"
}
New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
$Text = Get-Content -Raw -Encoding UTF8 -LiteralPath $SourceIdf
$Text = Replace-UniqueText -InputText $Text `
    -Pattern '(?s)(<name>BAR1_Size</name>\s*.*?<value>)256(</value>)' `
    -Replacement '${1}512${2}' `
    -Description 'BAR1_Size=256 source value'
$Text = Replace-UniqueText -InputText $Text `
    -Pattern '(?s)(<name>BAR1_Enable</name>\s*<value>)false(</value>)' `
    -Replacement '${1}true${2}' `
    -Description 'BAR1_Enable=false source value'

# Parse before writing so a malformed replacement can never become generator input.
try {
    $StagingXml = [xml]$Text
} catch {
    throw "BAR1 staging IDF is not valid XML: $($_.Exception.Message)"
}
Require-UniqueParamValue -Document $StagingXml -Name 'BAR1_Enable' -Expected 'true'
Require-UniqueParamValue -Document $StagingXml -Name 'BAR1_Size' -Expected '512'
Require-UniqueParamValue -Document $StagingXml -Name 'BAR1_Size_Unit' -Expected 'Bytes'
Require-UniqueParamValue -Document $StagingXml -Name 'BAR1_MASK_EN' -Expected 'false'
Require-UniqueParamValue -Document $StagingXml -Name 'BAR1_MASK' -Expected "31'h0"
[IO.File]::WriteAllText($StageIdf, $Text, [Text.UTF8Encoding]::new($false))
if (Test-Path -LiteralPath $SourceIndex -PathType Leaf) {
    Copy-Item -LiteralPath $SourceIndex -Destination (Join-Path $StageRoot 'index.xml') -Force
}

Write-Host "INFO: prepared BAR1 staging IDF at $StageIdf"
Write-Host 'INFO: target Logos2 / PG2L50H / FBG484 / -6; BAR1 size 512 Bytes'
if (-not $Execute) {
    Write-Host 'INFO: dry run only; pass -Execute to invoke ip_generate.exe'
    return
}
if (-not (Test-Path -LiteralPath $Generator -PathType Leaf)) {
    throw "PDS IP generator not found: $Generator"
}

& $Generator -i $StageIdf -m $StageRoot -family Logos2 -device PG2L50H -pack FBG484 -speed -6 -log (Join-Path $StageRoot 'generate.log')
if ($LASTEXITCODE -ne 0) {
    throw "PDS IP generation failed with exit code $LASTEXITCODE"
}
Write-Host 'INFO: BAR1 staging generation completed; canonical IP was not modified'
