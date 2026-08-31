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
$ProvenanceScript = Join-Path $PSScriptRoot 'build_provenance.ps1'
$PdsShell = Join-Path $PdsBin 'pds_shell.exe'
$Vsim = Join-Path $QuestaBin 'vsim.exe'

if (-not (Test-Path -LiteralPath $ProvenanceScript -PathType Leaf)) {
    throw "PDS provenance helper not found: $ProvenanceScript"
}
. $ProvenanceScript

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
    $LogFile = Join-Path $LogDir "pds-$RunTo.log"
    $ManifestPath = Get-PdsProvenanceManifestPath -ProjectRoot $ProjectRoot
    $RunId = ([Guid]::NewGuid().ToString('N')).ToLowerInvariant()
    $InputPaths = @()
    $InputRecords = @()
    $Manifest = [ordered]@{
        schema_version = 1
        project = 'pcie_dma_test_100h'
        run_id = $RunId
        run_to = $RunTo
        status = 'running'
        valid = $false
        started_utc = (Get-Date).ToUniversalTime().ToString('o')
        completed_utc = $null
        target = [ordered]@{
            board = 'RK3568+PG2L50H100H'
            fpga = 'PG2L50H-6IFBG484'
            pds_family = 'Logos2'
            pds_device = 'PG2L50H'
            pds_package = 'FBG484'
            pds_speedgrade = '-6'
        }
        inputs = @()
        artifacts = @()
    }

    Write-PdsProvenanceManifest `
        -Path $ManifestPath `
        -Manifest $Manifest `
        -RunId $RunId

    $PreviousRunTo = $env:PDS_RUN_TO
    $PreviousRunId = $env:PDS_RUN_ID
    $env:PDS_RUN_TO = $RunTo
    $env:PDS_RUN_ID = $RunId

    try {
        $InputPaths = Get-PdsCanonicalInputPaths -ProjectRoot $ProjectRoot
        $InputRecords = Get-PdsFileRecords `
            -ProjectRoot $ProjectRoot `
            -RelativePaths $InputPaths
        $Manifest.inputs = $InputRecords
        Write-PdsProvenanceManifest `
            -Path $ManifestPath `
            -Manifest $Manifest `
            -RunId $RunId

        Assert-Executable -Path $PdsShell -Description 'PDS shell'
        New-Item -ItemType Directory -Force -Path $PdsWorkDir, $LogDir |
            Out-Null

        Write-Host "INFO: running PDS through stage '$RunTo' (run $RunId)"
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

        $Manifest.status = if ($RunTo -eq 'gen_bit_stream') {
            'complete'
        } else {
            'partial'
        }
        if ($RunTo -eq 'gen_bit_stream') {
            $LogText = Get-Content -Raw -LiteralPath $LogFile
            $RunMarker = "INFO: PDS_RUN_ID=$RunId"
            $CompleteMarker = "INFO: PDS_RUN_COMPLETE=$RunId"
            if ([regex]::Matches($LogText, [regex]::Escape($RunMarker)).Count -ne 1 -or
                [regex]::Matches($LogText, [regex]::Escape($CompleteMarker)).Count -ne 1) {
                throw "PDS log does not contain exactly one run marker and completion marker: $LogFile"
            }
            Assert-PdsFileRecordsMatch `
                -Expected $InputRecords `
                -Actual (Get-PdsFileRecords -ProjectRoot $ProjectRoot -RelativePaths $InputPaths) `
                -Description 'PDS canonical inputs'
            $Manifest.artifacts = Get-PdsFileRecords `
                -ProjectRoot $ProjectRoot `
                -RelativePaths (Get-PdsArtifactPaths)
            $Manifest.valid = $true
        }
        $Manifest.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
        Write-PdsProvenanceManifest `
            -Path $ManifestPath `
            -Manifest $Manifest `
            -RunId $RunId
    } catch {
        $Manifest.status = 'failed'
        $Manifest.valid = $false
        $Manifest.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
        $Manifest.error = $_.Exception.Message
        try {
            Write-PdsProvenanceManifest `
                -Path $ManifestPath `
                -Manifest $Manifest `
                -RunId $RunId
        } catch {
            Write-Warning "Unable to publish failed provenance manifest: $($_.Exception.Message)"
        }
        throw
    } finally {
        $env:PDS_RUN_TO = $PreviousRunTo
        $env:PDS_RUN_ID = $PreviousRunId
    }

    Write-Host "INFO: provenance manifest status '$($Manifest.status)' at $ManifestPath"

    Write-Host "INFO: PDS stage '$RunTo' completed"
}

function Invoke-ModelSim {
    param(
        [Parameter(Mandatory)]
        [string]$DoFileName,

        [Parameter(Mandatory)]
        [string]$LogFileName
    )

    Assert-Executable -Path $Vsim -Description 'ModelSim/QuestaSim executable'

    $DoFile = Join-Path $PSScriptRoot $DoFileName
    if (-not (Test-Path -LiteralPath $DoFile -PathType Leaf)) {
        throw "Simulation flow is not implemented yet: $DoFile"
    }

    $LogFile = Join-Path $LogDir $LogFileName
    $RunId = ([Guid]::NewGuid().ToString('N')).ToLowerInvariant()
    $PreviousRunId = $env:SIM_RUN_ID
    $env:SIM_RUN_ID = $RunId

    Push-Location $ProjectRoot
    try {
        Write-Host "INFO: running simulation script '$DoFileName' (run $RunId)"
        & $Vsim -c -do "do scripts/$DoFileName"
        if ($LASTEXITCODE -ne 0) {
            throw "Simulation failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
        $env:SIM_RUN_ID = $PreviousRunId
    }

    if (-not (Test-Path -LiteralPath $LogFile -PathType Leaf)) {
        throw "Simulation log not found: $LogFile"
    }

    $LogText = Get-Content -Raw -LiteralPath $LogFile
    $RunMarker = "INFO: SIM_RUN_ID=$RunId"
    if ([regex]::Matches($LogText, [regex]::Escape($RunMarker)).Count -ne 1) {
        throw "Simulation log does not contain exactly one matching run marker: $LogFile"
    }

    $PassPattern = '(?m)^(?:#\s*)?TEST PASS\s*$'
    if ([regex]::Matches($LogText, $PassPattern).Count -ne 1) {
        throw "Simulation log does not contain exactly one TEST PASS line: $LogFile"
    }

    Write-Host "INFO: simulation run $RunId passed"
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
        Invoke-ModelSim `
            -DoFileName 'run_behav.do' `
            -LogFileName 'sim-behav.log'
    }
    'sim-post-syn' {
        Invoke-ModelSim `
            -DoFileName 'run_post_syn.do' `
            -LogFileName 'sim-post-syn.log'
    }
    'sim-post-pnr-func' {
        Invoke-ModelSim `
            -DoFileName 'run_post_pnr_func.do' `
            -LogFileName 'sim-post-pnr-func.log'
    }
    'sim-post-pnr-timing' {
        Invoke-ModelSim `
            -DoFileName 'run_post_pnr_timing.do' `
            -LogFileName 'sim-post-pnr-timing.log'
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
