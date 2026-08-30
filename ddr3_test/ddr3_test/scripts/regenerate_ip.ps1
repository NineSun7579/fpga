param(
    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin',

    [string]$StagingRoot = ''
)

# Regenerate the active DDR3 instance in an ignored staging directory. This
# script never modifies the canonical vendor IP directory.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CanonicalIpRoot = Join-Path $ProjectRoot 'ip_core\ddr3'
$CanonicalIdf = Join-Path $CanonicalIpRoot 'ddr3.idf'
$SeedIpRoot = Join-Path $ProjectRoot 'ip_backup\20250108100125\ddr3'
$SeedIdf = Join-Path $SeedIpRoot 'ddr3.idf'
$IpGenerator = Join-Path $PdsBin 'ip_generate.exe'
$BuildRoot = Join-Path $ProjectRoot 'build'
$LogRoot = Join-Path $BuildRoot 'logs'

function Assert-File {
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }
}

function Assert-Directory {
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Description not found: $Path"
    }
}

function Assert-UnderProjectBuild {
    param([Parameter(Mandatory)][string]$Path)

    $ResolvedProject = [IO.Path]::GetFullPath($ProjectRoot)
    $ResolvedBuild = [IO.Path]::GetFullPath($BuildRoot)
    $ResolvedPath = [IO.Path]::GetFullPath($Path)
    $ProjectPrefix = $ResolvedProject.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    $BuildPrefix = $ResolvedBuild.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar

    if (-not $ResolvedBuild.StartsWith(
        $ProjectPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Project build root is outside project: $ResolvedBuild"
    }
    if (-not $ResolvedPath.StartsWith(
        $BuildPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing staging path outside project build/: $ResolvedPath"
    }
}

function Get-IdfParameterEntries {
    param([Parameter(Mandatory)][xml]$IdfXml)

    foreach ($Parameter in $IdfXml.SelectNodes("//*[local-name()='param']")) {
        if ($null -ne $Parameter.name) {
            [pscustomobject]@{
                Name = [string]$Parameter.name
                Value = [string]$Parameter.value
            }
        }
    }
}

Assert-Directory -Path $CanonicalIpRoot -Description 'canonical DDR3 IP directory'
Assert-File -Path $CanonicalIdf -Description 'canonical DDR3 IDF'
Assert-Directory -Path $SeedIpRoot -Description 'legacy PG2L50H seed directory'
Assert-File -Path $SeedIdf -Description 'legacy PG2L50H seed IDF'
Assert-File -Path $IpGenerator -Description 'PDS IP generator'
$CanonicalIdfHashBefore = (Get-FileHash -LiteralPath $CanonicalIdf `
    -Algorithm SHA256).Hash

try {
    [xml]$CanonicalIdfXml = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $CanonicalIdf
    [xml]$SeedIdfXml = Get-Content -Raw -Encoding UTF8 -LiteralPath $SeedIdf
} catch {
    throw 'Canonical or seed DDR3 IDF is not valid XML'
}

$SeedHeader = $SeedIdfXml.ip_inst.header
if ([string]$SeedHeader.family -ne 'Logos2' -or
    [string]$SeedHeader.device -ne 'PG2L50H' -or
    [string]$SeedHeader.package -ne 'FBG484' -or
    [string]$SeedHeader.speedgrade -ne '-6') {
    throw 'Legacy seed IDF does not target Logos2 / PG2L50H / FBG484 / -6'
}
if ([string]$SeedHeader.generator.version -ne '2022.2-SP6.1') {
    throw "Unexpected legacy seed generator: $($SeedHeader.generator.version)"
}

$CanonicalParameters = @(Get-IdfParameterEntries -IdfXml $CanonicalIdfXml)
$SeedParameters = @(Get-IdfParameterEntries -IdfXml $SeedIdfXml)
$CanonicalDeviceFlags = @(
    $CanonicalParameters | Where-Object {
        [string]::Equals($_.Name, 'DEVICE_100H_EN',
            [StringComparison]::Ordinal)
    }
)
$SeedDeviceFlags = @(
    $SeedParameters | Where-Object {
        [string]::Equals($_.Name, 'DEVICE_100H_EN',
            [StringComparison]::Ordinal)
    }
)
if ($CanonicalDeviceFlags.Count -ne 1 -or
    $SeedDeviceFlags.Count -ne 1 -or
    $CanonicalDeviceFlags[0].Value -ne 'true' -or
    $SeedDeviceFlags[0].Value -ne 'false') {
    throw 'Expected canonical/seed DEVICE_100H_EN values are not true/false'
}

# IDF parameter order is not stable, and names that differ only by case exist.
# Compare a case-sensitive multiset of complete name/value entries.
$ParameterSeparator = [char]0x1f
$CanonicalParameterSet = @(
    $CanonicalParameters |
        Where-Object {
            -not [string]::Equals($_.Name, 'DEVICE_100H_EN',
                [StringComparison]::Ordinal)
        } |
        ForEach-Object { $_.Name + $ParameterSeparator + $_.Value } |
        Sort-Object -CaseSensitive
)
$SeedParameterSet = @(
    $SeedParameters |
        Where-Object {
            -not [string]::Equals($_.Name, 'DEVICE_100H_EN',
                [StringComparison]::Ordinal)
        } |
        ForEach-Object { $_.Name + $ParameterSeparator + $_.Value } |
        Sort-Object -CaseSensitive
)
$UnexpectedParameterDifferences = @(
    Compare-Object `
        -ReferenceObject $CanonicalParameterSet `
        -DifferenceObject $SeedParameterSet `
        -CaseSensitive
)
if ($UnexpectedParameterDifferences.Count -gt 0) {
    $DifferenceSummary = @(
        $UnexpectedParameterDifferences | ForEach-Object {
            $DisplayValue = ([string]$_.InputObject).Replace(
                $ParameterSeparator, '=')
            "$($_.SideIndicator) $DisplayValue"
        }
    )
    throw "Seed parameters differ from canonical configuration: $($DifferenceSummary -join '; ')"
}

if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
    $StagingRoot = Join-Path $BuildRoot 'ipgen\pg2l50h'
} elseif (-not [IO.Path]::IsPathRooted($StagingRoot)) {
    $StagingRoot = Join-Path $ProjectRoot $StagingRoot
}
$StagingRoot = [IO.Path]::GetFullPath($StagingRoot)
Assert-UnderProjectBuild -Path $StagingRoot

New-Item -ItemType Directory -Force -Path $BuildRoot, $LogRoot | Out-Null
if (Test-Path -LiteralPath $StagingRoot) {
    Remove-Item -LiteralPath $StagingRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $StagingRoot | Out-Null
Write-Host "INFO: copying validated PG2L50H seed to staging: $StagingRoot"
Copy-Item -Path (Join-Path $SeedIpRoot '*') `
    -Destination $StagingRoot `
    -Recurse `
    -Force

$StagedIdf = Join-Path $StagingRoot 'ddr3.idf'
$GeneratorLog = Join-Path $StagingRoot 'generate.log'
$ConsoleLog = Join-Path $LogRoot 'ipgen-pg2l50h.log'

Push-Location $StagingRoot
try {
    Write-Host 'INFO: generating Logos2 / PG2L50H / FBG484 / -6 IP assets'
    & $IpGenerator `
        -i $StagedIdf `
        -family Logos2 `
        -device PG2L50H `
        -pack FBG484 `
        -speed -6 `
        -log generate.log `
        2>&1 | Tee-Object -FilePath $ConsoleLog
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($ExitCode -ne 0) {
    throw "PDS IP generation failed with exit code $ExitCode. See $ConsoleLog"
}
Assert-File -Path $StagedIdf -Description 'staged DDR3 IDF'
Assert-File -Path $GeneratorLog -Description 'IP generator log'

try {
    [xml]$IdfXml = Get-Content -Raw -Encoding UTF8 -LiteralPath $StagedIdf
} catch {
    throw "Staged DDR3 IDF is not valid XML: $StagedIdf"
}

$Header = $IdfXml.ip_inst.header
$Device = [string]$Header.device
$Package = [string]$Header.package
$Family = [string]$Header.family
$Speed = [string]$Header.speedgrade
$GeneratorVersion = [string]$Header.generator.version
$Device100HParameter = @(
    $IdfXml.SelectNodes("//*[local-name()='param']") |
        Where-Object { [string]$_.name -eq 'DEVICE_100H_EN' } |
        ForEach-Object { [string]$_.value }
)

if ($Family -ne 'Logos2' -or $Device -ne 'PG2L50H' -or
    $Package -ne 'FBG484' -or $Speed -ne '-6') {
    throw "Staged IDF metadata mismatch: $Family / $Device / $Package / $Speed"
}
if ($GeneratorVersion -ne '2022.2-SP6.4') {
    throw "Unexpected IP generator version: $GeneratorVersion"
}
if ($Device100HParameter.Count -ne 1 -or $Device100HParameter[0] -ne 'false') {
    throw "Generated DEVICE_100H_EN must be false for PG2L50H: $($Device100HParameter -join ', ')"
}

foreach ($RelativePath in @(
        'ddr3.v',
        'ddr3_ddrphy_top.v',
        'rtl\ddrphy\ddr3_slice_top_v1_10.v',
        'example_design\rtl\test_ddr.v',
        'pnr\ddr_test.fdc',
        'pnr\ddr3.rcf',
        'sim\modelsim\sim_file_list.f')) {
    Assert-File -Path (Join-Path $StagingRoot $RelativePath) `
        -Description "staged DDR3 asset $RelativePath"
}

$DdrPhySlicePath = Join-Path $StagingRoot `
    'rtl\ddrphy\ddr3_slice_top_v1_10.v'
$DdrPhySliceText = Get-Content -Raw -Encoding UTF8 `
    -LiteralPath $DdrPhySlicePath
if ($DdrPhySliceText -notmatch '\.CLKOUT4_SYN_EN\s*\("TRUE"\s*\)' -or
    $DdrPhySliceText -notmatch '\.INTERNAL_FB\s*\("CLKOUT4"\s*\)') {
    throw 'Generated DDR PHY slice does not contain the PG2L50H PPLL branch'
}

$CanonicalIdfHashAfter = (Get-FileHash -LiteralPath $CanonicalIdf `
    -Algorithm SHA256).Hash
if ($CanonicalIdfHashAfter -ne $CanonicalIdfHashBefore) {
    throw "Canonical DDR3 IDF changed during staging generation: $CanonicalIdf"
}

Write-Host "INFO: staged IDF target: $Family / $Device / $Package / $Speed"
Write-Host "INFO: generator version: $GeneratorVersion"
Write-Host "INFO: DEVICE_100H_EN raw value: $($Device100HParameter -join ', ')"
Write-Host 'INFO: seed parameters match canonical except DEVICE_100H_EN'
Write-Host 'INFO: generated DDR PHY slice uses CLKOUT4 feedback for PG2L50H'
Write-Host "INFO: canonical IDF SHA-256 unchanged: $CanonicalIdfHashAfter"
Write-Host 'INFO: staging output is review-only; canonical IP was not modified'
Write-Host "INFO: staged DDR3 IP regeneration completed: $StagingRoot"
