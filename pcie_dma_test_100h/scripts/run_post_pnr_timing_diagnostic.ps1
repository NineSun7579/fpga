param(
    [Parameter(Mandatory)]
    [string]$QuestaBin,

    [Parameter(Mandatory)]
    [string]$PdsRoot
)

# Run a diagnostic-only solver matrix. This script never changes the canonical
# S2-F level2 acceptance contract and never treats a completed matrix as PASS.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$LogDir = Join-Path $BuildRoot 'logs'
$DoFile = Join-Path $ProjectRoot 'sim\questa\run_post_pnr_timing_diagnostic.do'
$ResultFile = Join-Path $LogDir 'sim-post-pnr-timing-diagnostic.json'
$ResolvedQuestaBin = $QuestaBin
if (-not (Test-Path -LiteralPath (Join-Path $ResolvedQuestaBin 'vsim.exe') -PathType Leaf)) {
    $Win64Candidate = Join-Path $QuestaBin 'win64'
    if (Test-Path -LiteralPath (Join-Path $Win64Candidate 'vsim.exe') -PathType Leaf) {
        $ResolvedQuestaBin = $Win64Candidate
    }
}

$Vsim = Join-Path $ResolvedQuestaBin 'vsim.exe'
$Vmap = Join-Path $ResolvedQuestaBin 'vmap.exe'
foreach ($Executable in @(
        [pscustomobject]@{ Path = $Vsim; Description = 'QuestaSim executable' },
        [pscustomobject]@{ Path = $Vmap; Description = 'QuestaSim library mapper' }
    )) {
    if (-not (Test-Path -LiteralPath $Executable.Path -PathType Leaf)) {
        throw "$($Executable.Description) not found: $($Executable.Path)"
    }
}
if (-not (Test-Path -LiteralPath $DoFile -PathType Leaf)) {
    throw "Archived S2-F diagnostic DO entry not found: $DoFile"
}

$InputFiles = [ordered]@{
    TimingNetlist = Join-Path $ProjectRoot 'build\pds\generate_netlist\pcie_dma_test_sim.v'
    SlowSdf = Join-Path $ProjectRoot 'build\pds\generate_netlist\pcie_dma_test_sta.sdf'
    Testbench = Join-Path $ProjectRoot 'sim\questa\tb\tb_pcie_dma_post_pnr_timing.sv'
    V_FFASYN = Join-Path $PdsRoot 'arch\vendor\pango\verilog\bsim\V_FFASYN.v'
    V_DRM18K_E1 = Join-Path $PdsRoot 'arch\vendor\pango\verilog\bsim\V_DRM18K_E1.v'
}
foreach ($InputFile in $InputFiles.GetEnumerator()) {
    if (-not (Test-Path -LiteralPath $InputFile.Value -PathType Leaf)) {
        throw "Diagnostic input '$($InputFile.Key)' not found: $($InputFile.Value)"
    }
}

$InputHashes = [ordered]@{}
foreach ($InputFile in $InputFiles.GetEnumerator()) {
    $InputHashes[$InputFile.Key] = (Get-FileHash -Algorithm SHA256 -LiteralPath $InputFile.Value).Hash
}
$QuestaVersion = ((& $Vsim -version 2>&1) -join ' ').Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($QuestaVersion)) {
    throw "Failed to read QuestaSim version from $Vsim"
}

$RunId = ([Guid]::NewGuid().ToString('N')).ToLowerInvariant()
$DoFileForTcl = $DoFile.Replace('\', '/')
$PreviousRunId = $env:SIM_RUN_ID
$PreviousProjectRoot = $env:SIM_PROJECT_ROOT
$PreviousSolverLevel = $env:SIM_GLS_NEG_TCHK_LEVEL
$SolverLevels = @('level1', 'level2', 'level3')
$SimulatorExitCodes = [ordered]@{}
$Failures = [System.Collections.Generic.List[string]]::new()
$DiagnosticRunRoot = [IO.Path]::GetFullPath(
    (Join-Path $BuildRoot "sim\post_pnr_timing_diagnostic\$RunId")
)
$LauncherRunRoot = [IO.Path]::GetFullPath(
    (Join-Path $BuildRoot "sim\launcher\$RunId")
)

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
foreach ($SolverLevel in $SolverLevels) {
    $StaleLog = Join-Path $LogDir "sim-post-pnr-timing-diagnostic-$SolverLevel.log"
    if (Test-Path -LiteralPath $StaleLog -PathType Leaf) {
        Remove-Item -LiteralPath $StaleLog -Force
    }
}
$env:SIM_RUN_ID = $RunId
$env:SIM_PROJECT_ROOT = $ProjectRoot

try {
    foreach ($SolverLevel in $SolverLevels) {
        $LaunchDir = Join-Path $LauncherRunRoot $SolverLevel
        $SolverRunRoot = [IO.Path]::GetFullPath(
            (Join-Path $DiagnosticRunRoot $SolverLevel)
        )
        foreach ($ScopedPath in @($LaunchDir, $SolverRunRoot)) {
            $ExpectedParent = if ($ScopedPath -eq $LaunchDir) {
                $LauncherRunRoot
            } else {
                $DiagnosticRunRoot
            }
            if (-not $ScopedPath.StartsWith(
                    $ExpectedParent + [IO.Path]::DirectorySeparatorChar,
                    [StringComparison]::OrdinalIgnoreCase
                )) {
                throw "Refusing to manage a diagnostic path outside its run root: $ScopedPath"
            }
        }
        $ModelsimIni = Join-Path $LaunchDir 'modelsim.ini'
        New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
        $env:SIM_GLS_NEG_TCHK_LEVEL = $SolverLevel

        Push-Location $LaunchDir
        try {
            & $Vmap -c
            if ($LASTEXITCODE -ne 0) {
                $Failures.Add("$SolverLevel failed to create modelsim.ini with exit code $LASTEXITCODE")
                $SimulatorExitCodes[$SolverLevel] = $LASTEXITCODE
                continue
            }

            Write-Host "INFO: running PCIe S2-F diagnostic $SolverLevel (run $RunId)"
            & $Vsim -c -modelsimini $ModelsimIni -do "do {$DoFileForTcl}"
            $SimulatorExitCodes[$SolverLevel] = $LASTEXITCODE
            if ($LASTEXITCODE -ne 0) {
                $Failures.Add("$SolverLevel QuestaSim exited with code $LASTEXITCODE")
            }
        } finally {
            Pop-Location
            # Work libraries and launcher state are runtime-only. Remove each
            # exact solver directory before the next run to bound disk usage.
            foreach ($RuntimeDirectory in @($SolverRunRoot, $LaunchDir)) {
                if ([IO.Directory]::Exists($RuntimeDirectory)) {
                    [IO.Directory]::Delete($RuntimeDirectory, $true)
                }
            }
        }
    }
} finally {
    $env:SIM_RUN_ID = $PreviousRunId
    $env:SIM_PROJECT_ROOT = $PreviousProjectRoot
    $env:SIM_GLS_NEG_TCHK_LEVEL = $PreviousSolverLevel
    foreach ($EmptyRunRoot in @($DiagnosticRunRoot, $LauncherRunRoot)) {
        if ([IO.Directory]::Exists($EmptyRunRoot) -and
            [IO.Directory]::GetFileSystemEntries($EmptyRunRoot).Count -eq 0) {
            [IO.Directory]::Delete($EmptyRunRoot)
        }
    }
}

$Rows = [System.Collections.Generic.List[object]]::new()
foreach ($SolverLevel in $SolverLevels) {
    $LogFile = Join-Path $LogDir "sim-post-pnr-timing-diagnostic-$SolverLevel.log"
    if (-not (Test-Path -LiteralPath $LogFile -PathType Leaf)) {
        $Failures.Add("Diagnostic log not found for $SolverLevel")
        continue
    }

    $LogText = Get-Content -Raw -LiteralPath $LogFile
    foreach ($Marker in @(
            "INFO: SIM_RUN_ID=$RunId",
            "INFO: GLS_NEG_TCHK_LEVEL=$SolverLevel",
            'INFO: DIAGNOSTIC_ONLY=S2F_ACCEPTANCE_UNCHANGED',
            'SDF Backannotation Successfully Completed',
            'INFO: POST_PNR_TIMING_RESET_PATH_OK'
        )) {
        $Count = [regex]::Matches($LogText, [regex]::Escape($Marker)).Count
        if ($Count -ne 1) {
            $Failures.Add("$SolverLevel expected one marker '$Marker'; found $Count")
        }
    }

    $PassCount = [regex]::Matches($LogText, '(?m)^(?:#\s*)?TEST PASS\s*$').Count
    if ($PassCount -ne 1) {
        $Failures.Add("$SolverLevel expected one TEST PASS line; found $PassCount")
    }
    foreach ($ForbiddenMarker in @('SDF annotation error', 'Failed to find instance')) {
        if ($LogText -match [regex]::Escape($ForbiddenMarker)) {
            $Failures.Add("$SolverLevel contains '$ForbiddenMarker'")
        }
    }

    $SummaryMatches = [regex]::Matches(
        $LogText,
        '(?m)^#\s+Errors:\s*([0-9]+),\s*Warnings:\s*([0-9]+)(?:,\s*Suppressed Warnings:\s*([0-9]+))?'
    )
    if ($SummaryMatches.Count -eq 0) {
        $Failures.Add("$SolverLevel has no simulator error summary")
        continue
    }
    $FinalSummary = $SummaryMatches[$SummaryMatches.Count - 1]

    $Rows.Add([pscustomobject][ordered]@{
            SolverLevel = $SolverLevel
            VsimProcessExitCode = $SimulatorExitCodes[$SolverLevel]
            Vsim3004 = [regex]::Matches($LogText, '\(vsim-3004\)').Count
            Vsim8756 = [regex]::Matches($LogText, '\(vsim-8756\)').Count
            Vsim3316 = [regex]::Matches($LogText, '\(vsim-3316\)').Count
            Vsim3616 = [regex]::Matches($LogText, '\(vsim-3616\)').Count
            SetupErrors = [regex]::Matches(
                $LogText,
                '(?m)^#\s+\*\*\s+Error:\s+\$setup\b'
            ).Count
            HoldErrors = [regex]::Matches(
                $LogText,
                '(?m)^#\s+\*\*\s+Error:\s+\$hold\b'
            ).Count
            OtherTimingErrors = [regex]::Matches(
                $LogText,
                '(?m)^#\s+\*\*\s+Error:\s+\$(?:setuphold|recovery|removal|recrem|width|period)\b'
            ).Count
            SimulatorErrors = [int]$FinalSummary.Groups[1].Value
            SimulatorWarnings = [int]$FinalSummary.Groups[2].Value
            SuppressedWarnings = if ($FinalSummary.Groups[3].Success) {
                [int]$FinalSummary.Groups[3].Value
            } else {
                0
            }
            Log = $LogFile
        })
}

$Result = [pscustomobject][ordered]@{
    RunId = $RunId
    QuestaVersion = $QuestaVersion
    VsimProcessExitCodes = $SimulatorExitCodes
    DiagnosticCompleted = ($Failures.Count -eq 0)
    AcceptanceStatus = 'blocked'
    CanonicalAcceptanceChanged = $false
    InputSha256 = $InputHashes
    Solvers = @($Rows)
    Failures = @($Failures)
}
$Result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultFile -Encoding UTF8
$Rows | Format-Table -AutoSize

if ($Failures.Count -gt 0) {
    throw ("PCIe S2-F diagnostic failed with {0} issue(s):`n- {1}`nResult: {2}" -f `
            $Failures.Count, ($Failures -join "`n- "), $ResultFile)
}

Write-Host "INFO: S2-F diagnostic matrix completed; canonical acceptance remains blocked"
Write-Host "INFO: diagnostic result: $ResultFile"
