param(
    [ValidateSet(
        'env-check',
        'build',
        'sim-behav',
        'sim-post-syn',
        'sim-post-pnr-func',
        'sim-post-pnr-timing',
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
    [string]$RunTo = 'gen_bit_stream',

    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin',
    [string]$QuestaBin = 'C:\questasim64\win64',

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
$Vsim = Join-Path $QuestaBin 'vsim.exe'

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
            -project_name pcie_dma_test `
            2>&1 | Tee-Object -FilePath $LogFile

        if ($LASTEXITCODE -ne 0) {
            throw "PDS failed with exit code $LASTEXITCODE. See $LogFile"
        }
        if (Select-String -LiteralPath $LogFile -Pattern '^E:' -Quiet) {
            throw "PDS reported one or more errors despite exit code 0. See $LogFile"
        }
    } finally {
        $env:PDS_RUN_TO = $PreviousRunTo
    }

    Write-Host "INFO: PDS stage '$RunTo' completed"
}

function Invoke-ModelSim {
    param(
        [Parameter(Mandatory)]
        [string]$DoFileName
    )

    Assert-Executable -Path $Vsim -Description 'ModelSim/QuestaSim executable'

    $DoFile = Join-Path $PSScriptRoot $DoFileName
    if (-not (Test-Path -LiteralPath $DoFile -PathType Leaf)) {
        throw "Simulation flow is not implemented yet: $DoFile"
    }

    Push-Location $ProjectRoot
    try {
        Write-Host "INFO: running simulation script '$DoFileName'"
        & $Vsim -c -do "do scripts/$DoFileName"
        if ($LASTEXITCODE -ne 0) {
            throw "Simulation failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
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
        Assert-Executable -Path $Vsim -Description 'ModelSim/QuestaSim executable'
        & $PdsShell -version
        & $Vsim -version
    }
    'build' {
        Invoke-PdsBuild
    }
    'sim-behav' {
        Invoke-ModelSim -DoFileName 'run_behav.do'
    }
    'sim-post-syn' {
        Invoke-ModelSim -DoFileName 'run_post_syn.do'
    }
    'sim-post-pnr-func' {
        Invoke-ModelSim -DoFileName 'run_post_pnr_func.do'
    }
    'sim-post-pnr-timing' {
        Invoke-ModelSim -DoFileName 'run_post_pnr_timing.do'
    }
    'check-build' {
        if ($AllowKnownBaselineIssues) {
            & $CheckBuildScript -AllowKnownBaselineIssues
        } else {
            & $CheckBuildScript
        }
    }
    'clean-build' {
        Remove-BuildDirectory
    }
}
