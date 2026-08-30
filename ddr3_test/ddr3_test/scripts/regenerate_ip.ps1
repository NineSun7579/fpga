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

Assert-Directory -Path $CanonicalIpRoot -Description 'canonical DDR3 IP directory'
Assert-File -Path $CanonicalIdf -Description 'canonical DDR3 IDF'
Assert-File -Path $IpGenerator -Description 'PDS IP generator'
$CanonicalIdfHashBefore = (Get-FileHash -LiteralPath $CanonicalIdf `
    -Algorithm SHA256).Hash

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
Write-Host "INFO: copying canonical DDR3 IP to staging: $StagingRoot"
Copy-Item -Path (Join-Path $CanonicalIpRoot '*') `
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
if ($Device100HParameter.Count -eq 0) {
    throw 'DEVICE_100H_EN parameter was not found; manual parameter review is required'
}

foreach ($RelativePath in @(
        'ddr3.v',
        'ddr3_ddrphy_top.v',
        'example_design\rtl\test_ddr.v',
        'pnr\ddr_test.fdc',
        'pnr\ddr3.rcf',
        'sim\modelsim\sim_file_list.f')) {
    Assert-File -Path (Join-Path $StagingRoot $RelativePath) `
        -Description "staged DDR3 asset $RelativePath"
}

$CanonicalIdfHashAfter = (Get-FileHash -LiteralPath $CanonicalIdf `
    -Algorithm SHA256).Hash
if ($CanonicalIdfHashAfter -ne $CanonicalIdfHashBefore) {
    throw "Canonical DDR3 IDF changed during staging generation: $CanonicalIdf"
}

Write-Host "INFO: staged IDF target: $Family / $Device / $Package / $Speed"
Write-Host "INFO: generator version: $GeneratorVersion"
Write-Host "INFO: DEVICE_100H_EN raw value: $($Device100HParameter -join ', ')"
Write-Host "INFO: canonical IDF SHA-256 unchanged: $CanonicalIdfHashAfter"
Write-Host 'INFO: staging output is review-only; canonical IP was not modified'
Write-Host "INFO: staged DDR3 IP regeneration completed: $StagingRoot"
