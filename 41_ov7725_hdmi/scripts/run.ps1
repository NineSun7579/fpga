param(
    [ValidateSet(
        'env-check',
        'build',
        'check-build',
        'clean-build'
    )]
    [string]$Action = 'build',

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

    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin',

    [switch]$AllowKnownBaselineIssues
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$PdsWorkDir = Join-Path $BuildRoot 'pds'
$LogDir = Join-Path $BuildRoot 'logs'
$BuildScript = Join-Path $PSScriptRoot 'build.tcl'
$CheckBuildScript = Join-Path $PSScriptRoot 'check_build.ps1'
$PdsShell = Join-Path $PdsBin 'pds_shell.exe'

function Assert-Executable {
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

function Invoke-PdsBuild {
    Assert-Executable -Path $PdsShell -Description 'PDS shell'

    New-Item -ItemType Directory -Force -Path $PdsWorkDir, $LogDir |
        Out-Null

    $LogFile = Join-Path $LogDir "pds-$RunTo.log"
    $PreviousRunTo = $env:PDS_RUN_TO
    $env:PDS_RUN_TO = $RunTo

    try {
        Write-Host "INFO: running PDS through stage '$RunTo'"
        & $PdsShell `
            -file $BuildScript `
            -work_dir $PdsWorkDir `
            -project_name ov7725_hdmi `
            2>&1 | Tee-Object -FilePath $LogFile

        if ($LASTEXITCODE -ne 0) {
            throw "PDS failed with exit code $LASTEXITCODE. See $LogFile"
        }
        if (Select-String -LiteralPath $LogFile -Pattern '^E:' -Quiet) {
            throw "PDS reported one or more errors despite exit code 0. See $LogFile"
        }

        $ExpectedMarker = if ($RunTo -eq 'gen_bit_stream') {
            'INFO: OV7725 HDMI implementation completed'
        } else {
            "INFO: requested stage $RunTo completed"
        }
        if (-not (Select-String `
            -LiteralPath $LogFile `
            -SimpleMatch $ExpectedMarker `
            -Quiet)) {
            throw "PDS log is missing the stage completion marker: $ExpectedMarker"
        }
    } finally {
        $env:PDS_RUN_TO = $PreviousRunTo
    }

    Write-Host "INFO: PDS stage '$RunTo' completed"
}

function Remove-BuildDirectory {
    if (-not (Test-Path -LiteralPath $BuildRoot)) {
        Write-Host 'INFO: build directory does not exist'
        return
    }

    $ResolvedProject = [IO.Path]::GetFullPath($ProjectRoot)
    $ResolvedBuild = [IO.Path]::GetFullPath($BuildRoot)
    $ExpectedPrefix = $ResolvedProject.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar

    if (-not $ResolvedBuild.StartsWith(
        $ExpectedPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to remove directory outside project: $ResolvedBuild"
    }
    if ([IO.Path]::GetFileName($ResolvedBuild) -ne 'build') {
        throw "Refusing to remove unexpected directory: $ResolvedBuild"
    }

    Remove-Item -LiteralPath $ResolvedBuild -Recurse -Force
    Write-Host "INFO: removed $ResolvedBuild"
}

switch ($Action) {
    'env-check' {
        Assert-Executable -Path $PdsShell -Description 'PDS shell'
        & $PdsShell -version
    }
    'build' {
        Invoke-PdsBuild
    }
    'check-build' {
        & $CheckBuildScript `
            -RunTo $RunTo `
            -AllowKnownBaselineIssues:$AllowKnownBaselineIssues
    }
    'clean-build' {
        Remove-BuildDirectory
    }
}
