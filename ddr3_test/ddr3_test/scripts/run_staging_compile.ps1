param(
    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin',

    [string]$StagingRoot = '',

    [string]$ScratchRoot = '',

    [string]$RunId = ''
)

# Regenerate and compile the PG2L50H DDR3 staging design in a unique run
# directory. The canonical IP tree is hashed before and after the run.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectBuildRoot = Join-Path $ProjectRoot 'build'
$RegenerateScript = Join-Path $PSScriptRoot 'regenerate_ip.ps1'
$BuildScript = Join-Path $PSScriptRoot 'build_staging_compile.tcl'
$CheckScript = Join-Path $PSScriptRoot 'check_staging_compile.ps1'
$PdsShell = Join-Path $PdsBin 'pds_shell.exe'

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

function Get-CanonicalHashes {
    $RelativePaths = @(
        'ip_core\ddr3\ddr3.idf',
        'ip_core\ddr3\ddr3.v',
        'ip_core\ddr3\rtl\ddrphy\ddr3_slice_top_v1_10.v',
        'ip_core\ddr3\example_design\rtl\test_ddr.v'
    )
    $Hashes = [ordered]@{}

    foreach ($RelativePath in $RelativePaths) {
        $Path = Join-Path $ProjectRoot $RelativePath
        Assert-File -Path $Path -Description "canonical DDR3 input $RelativePath"
        $Hashes[$RelativePath.Replace('\', '/')] = (
            Get-FileHash -LiteralPath $Path -Algorithm SHA256
        ).Hash
    }

    return $Hashes
}

function Restore-EnvironmentValue {
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [AllowNull()]
        [string]$Value
    )

    if ($null -eq $Value) {
        Remove-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
    } else {
        Set-Item -Path "Env:$Name" -Value $Value
    }
}

function Protect-LicenseCheckoutLine {
    param([Parameter(ValueFromPipeline)][AllowNull()]$Line)

    process {
        if ([string]$Line -match '(?i)^License checkout:') {
            'INFO: tool license checkout succeeded; details redacted'
        } else {
            $Line
        }
    }
}

function Protect-ToolLog {
    param([Parameter(Mandatory)][string]$Path)

    $Lines = @(Get-Content -Encoding UTF8 -LiteralPath $Path)
    $ProtectedLines = @($Lines | Protect-LicenseCheckoutLine)
    if (-not [System.Linq.Enumerable]::SequenceEqual(
        [string[]]$Lines,
        [string[]]$ProtectedLines
    )) {
        $ProtectedLines | Set-Content -Encoding UTF8 -LiteralPath $Path
    }
}

foreach ($RequiredFile in @(
        $RegenerateScript,
        $BuildScript,
        $CheckScript,
        $PdsShell
    )) {
    Assert-File -Path $RequiredFile -Description 'M2-B2 required file'
}

if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
    $StagingRoot = Join-Path $ProjectBuildRoot 'ipgen\pg2l50h'
} elseif (-not [IO.Path]::IsPathRooted($StagingRoot)) {
    $StagingRoot = Join-Path $ProjectRoot $StagingRoot
}
$StagingRoot = [IO.Path]::GetFullPath($StagingRoot)

if ([string]::IsNullOrWhiteSpace($ScratchRoot)) {
    $ScratchRoot = Join-Path $ProjectBuildRoot 'm2b2_compile'
} elseif (-not [IO.Path]::IsPathRooted($ScratchRoot)) {
    $ScratchRoot = Join-Path $ProjectRoot $ScratchRoot
}
$ScratchRoot = [IO.Path]::GetFullPath($ScratchRoot)

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = [guid]::NewGuid().ToString('N')
}
if ($RunId -notmatch '^[A-Za-z0-9_-]+$') {
    throw "RunId contains unsupported characters: $RunId"
}

$RunRoot = Join-Path $ScratchRoot $RunId
if (Test-Path -LiteralPath $RunRoot) {
    throw "M2-B2 run directory already exists: $RunRoot"
}

$PdsWorkDir = Join-Path $RunRoot 'pds'
$LogDir = Join-Path $RunRoot 'logs'
$TempRoot = Join-Path $RunRoot 'tmp'
$PdsLog = Join-Path $LogDir 'pds-compile.log'
$SummaryPath = Join-Path $RunRoot 'summary.json'

New-Item -ItemType Directory -Force -Path `
    $PdsWorkDir, $LogDir, $TempRoot | Out-Null

$Summary = [ordered]@{
    schema_version = 1
    run_id = $RunId
    status = 'running'
    target = 'Logos2 / PG2L50H / FBG484 / -6'
    top_module = 'test_ddr'
    source_count = 18
    port_count = 0
    pds_exit_code = $null
    error_records = $null
    warning_records = $null
    canonical_hashes_before = Get-CanonicalHashes
    canonical_hashes_after = $null
    failure = $null
}
$Summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 `
    -LiteralPath $SummaryPath

$PreviousTemp = $env:TEMP
$PreviousTmp = $env:TMP
$PreviousStagingRoot = $env:DDR3_STAGING_ROOT
$PreviousRunId = $env:M2B2_RUN_ID

try {
    $env:TEMP = $TempRoot
    $env:TMP = $TempRoot

    Write-Host "INFO: M2-B2 run id: $RunId"
    Write-Host "INFO: regenerating PG2L50H staging inputs"
    & $RegenerateScript -PdsBin $PdsBin -StagingRoot $StagingRoot

    $TopPath = Join-Path $StagingRoot 'example_design\rtl\test_ddr.v'
    Assert-File -Path $TopPath -Description 'staged PG2L50H test_ddr top'
    $TopText = Get-Content -Raw -Encoding UTF8 -LiteralPath $TopPath
    $HeaderMatch = [regex]::Match(
        $TopText,
        '(?s)\bmodule\s+test_ddr\s*#\s*\(.*?\)\s*\((?<ports>.*?)\)\s*;'
    )
    if (-not $HeaderMatch.Success) {
        throw 'Unable to parse staged test_ddr module header'
    }
    $PortCount = [regex]::Matches(
        $HeaderMatch.Groups['ports'].Value,
        '(?m)^\s*(?:input|output|inout)\b'
    ).Count
    if ($PortCount -ne 26) {
        throw "Staged test_ddr port count must be 26, found $PortCount"
    }
    if ($TopText -notmatch '\bI_ips_ddr_top\b') {
        throw 'Staged test_ddr is missing the I_ips_ddr_top instance'
    }
    $Summary.port_count = $PortCount

    $env:DDR3_STAGING_ROOT = $StagingRoot
    $env:M2B2_RUN_ID = $RunId

    Write-Host 'INFO: compiling staging design with PDS'
    & $PdsShell `
        -file $BuildScript `
        -work_dir $PdsWorkDir `
        -project_name ddr3_m2b2 `
        2>&1 | Protect-LicenseCheckoutLine |
        Tee-Object -FilePath $PdsLog
    $PdsExitCode = $LASTEXITCODE
    $Summary.pds_exit_code = $PdsExitCode

    foreach ($ToolLog in @(Get-ChildItem -LiteralPath $RunRoot `
            -File -Filter '*.log' -Recurse -ErrorAction SilentlyContinue)) {
        Protect-ToolLog -Path $ToolLog.FullName
    }

    if ($PdsExitCode -ne 0) {
        throw "PDS staging compile failed with exit code $PdsExitCode"
    }

    Assert-File -Path $PdsLog -Description 'M2-B2 PDS compile log'
    $LogText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PdsLog
    $Summary.error_records = [regex]::Matches($LogText, '(?m)^E:').Count
    $Summary.warning_records = [regex]::Matches($LogText, '(?m)^W:').Count
    if ($Summary.error_records -ne 0) {
        throw "PDS staging compile log contains $($Summary.error_records) error record(s)"
    }
    if ($LogText -match '(?i)^License checkout:') {
        throw 'PDS staging compile log contains unredacted license checkout details'
    }

    foreach ($Artifact in @(
            'compile\test_ddr_comp.adf',
            'compile\test_ddr.cmr',
            'compile\cmr.db'
        )) {
        $ArtifactPath = Join-Path $PdsWorkDir $Artifact
        Assert-File -Path $ArtifactPath -Description "M2-B2 artifact $Artifact"
        if ((Get-Item -LiteralPath $ArtifactPath).Length -le 0) {
            throw "M2-B2 artifact is empty: $ArtifactPath"
        }
    }

    $Summary.canonical_hashes_after = Get-CanonicalHashes
    foreach ($Key in $Summary.canonical_hashes_before.Keys) {
        if ($Summary.canonical_hashes_before[$Key] -cne `
            $Summary.canonical_hashes_after[$Key]) {
            throw "Canonical DDR3 input changed during M2-B2: $Key"
        }
    }

    $Summary.status = 'complete'
    $Summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 `
        -LiteralPath $SummaryPath

    & $CheckScript -StagingRoot $StagingRoot -RunRoot $RunRoot
    Write-Host "INFO: M2-B2 staging compile completed: $RunId"
} catch {
    $Summary.status = 'failed'
    $Summary.failure = $_.Exception.Message
    $Summary.canonical_hashes_after = Get-CanonicalHashes
    $Summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 `
        -LiteralPath $SummaryPath
    throw
} finally {
    Restore-EnvironmentValue -Name 'TEMP' -Value $PreviousTemp
    Restore-EnvironmentValue -Name 'TMP' -Value $PreviousTmp
    Restore-EnvironmentValue -Name 'DDR3_STAGING_ROOT' `
        -Value $PreviousStagingRoot
    Restore-EnvironmentValue -Name 'M2B2_RUN_ID' -Value $PreviousRunId
}
