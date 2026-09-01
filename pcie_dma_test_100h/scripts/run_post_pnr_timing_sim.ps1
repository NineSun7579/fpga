param(
    [Parameter(Mandatory)]
    [string]$QuestaBin
)

# Run the archived S2-F flow without changing the canonical PDS build launcher.
# Tool installation and license configuration remain external inputs.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $ProjectRoot 'build'
$LogDir = Join-Path $BuildRoot 'logs'
$DoFile = Join-Path $ProjectRoot 'sim\questa\run_post_pnr_timing.do'
$LogFile = Join-Path $LogDir 'sim-post-pnr-timing.log'
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
    throw "Archived S2-F DO entry not found: $DoFile"
}

$RunId = ([Guid]::NewGuid().ToString('N')).ToLowerInvariant()
$LaunchDir = Join-Path $BuildRoot "sim\launcher\$RunId"
$ModelsimIni = Join-Path $LaunchDir 'modelsim.ini'
$DoFileForTcl = $DoFile.Replace('\', '/')
$PreviousRunId = $env:SIM_RUN_ID
$PreviousProjectRoot = $env:SIM_PROJECT_ROOT
$SimulatorExitCode = $null

New-Item -ItemType Directory -Force -Path $LaunchDir, $LogDir | Out-Null
$env:SIM_RUN_ID = $RunId
$env:SIM_PROJECT_ROOT = $ProjectRoot

Push-Location $LaunchDir
try {
    & $Vmap -c
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create run-scoped modelsim.ini with exit code $LASTEXITCODE"
    }

    Write-Host "INFO: running PCIe S2-F post-PNR timing simulation (run $RunId)"
    & $Vsim -c -modelsimini $ModelsimIni -do "do {$DoFileForTcl}"
    $SimulatorExitCode = $LASTEXITCODE
} finally {
    Pop-Location
    $env:SIM_RUN_ID = $PreviousRunId
    $env:SIM_PROJECT_ROOT = $PreviousProjectRoot
}

$Failures = [System.Collections.Generic.List[string]]::new()
if ($SimulatorExitCode -ne 0) {
    $Failures.Add("QuestaSim exited with code $SimulatorExitCode")
}
if (-not (Test-Path -LiteralPath $LogFile -PathType Leaf)) {
    throw "Simulation log not found: $LogFile"
}

$LogText = Get-Content -Raw -LiteralPath $LogFile
$RequiredMarkers = @(
    "INFO: SIM_RUN_ID=$RunId",
    'SDF Backannotation Successfully Completed',
    'INFO: POST_PNR_TIMING_RESET_PATH_OK'
)
foreach ($Marker in $RequiredMarkers) {
    $Count = [regex]::Matches($LogText, [regex]::Escape($Marker)).Count
    if ($Count -ne 1) {
        $Failures.Add("Expected exactly one marker '$Marker'; found $Count")
    }
}

$PassPattern = '(?m)^(?:#\s*)?TEST PASS\s*$'
$PassCount = [regex]::Matches($LogText, $PassPattern).Count
if ($PassCount -ne 1) {
    $Failures.Add("Expected exactly one TEST PASS line; found $PassCount")
}

$ForbiddenPatterns = [ordered]@{
    'SDF annotation error' = 'SDF annotation error'
    'SDF instance mismatch' = 'Failed to find instance'
    'generic timing violation' = 'Timing check violation'
    'negative timing-check diagnostic' = 'Negative timing check'
    'positive timing-check error' =
        '(?m)^#\s+\*\*\s+Error:\s+\$(?:setup|hold|setuphold|recovery|removal|recrem|width|period)\b'
    'nonzero simulator error summary' = '(?m)^#\s+Errors:\s*[1-9][0-9]*\b'
    'incomplete delayed timing model' = '\(vsim-8756\)'
    'unsolved negative timing limit' = '\(vsim-3004\)'
}
foreach ($Entry in $ForbiddenPatterns.GetEnumerator()) {
    if ($LogText -match $Entry.Value) {
        $Failures.Add("Simulation log contains $($Entry.Key)")
    }
}

if ($Failures.Count -gt 0) {
    throw ("PCIe S2-F simulation failed with {0} issue(s):`n- {1}`nLog: {2}" -f `
            $Failures.Count, ($Failures -join "`n- "), $LogFile)
}

Write-Host "INFO: PCIe S2-F simulation run $RunId passed"
