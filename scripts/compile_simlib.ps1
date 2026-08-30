param(
    [ValidateSet('ModelSim Simulator', 'QuestaSim Simulator')]
    [string]$Simulator = 'QuestaSim Simulator',

    [ValidateSet('USIM', 'VSIM', 'BOTH')]
    [string]$Library = 'BOTH',

    [string]$Family = 'Logos2',
    [ValidateSet('Verilog', 'VHDL', 'Verilog and VHDL')]
    [string]$Language = 'Verilog',
    [string]$PdsBin = 'E:\pango\PDS_2022.2-SP6.4\bin',
    [string]$SimulatorExecPath = 'C:\questasim64\win64',
    [string]$OutputDirectory = '',
    [switch]$SkipSimulatorValidation
)

# Keep simulator installation paths external and fail before PDS if they are
# unavailable. This prevents a misleading "library completed" message.
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PdsShell = Join-Path $PdsBin 'pds_shell.exe'
$CompileScript = Join-Path $PSScriptRoot 'compile_simlib.tcl'
$BuildRoot = Join-Path $RepoRoot 'build\simlib'
$WorkDirectory = Join-Path $RepoRoot 'build\pds-simlib'
$LogDirectory = Join-Path $RepoRoot 'build\logs'

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = $BuildRoot
}

function Assert-Executable {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }
}

function Assert-Directory {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Description not found: $Path"
    }
}

Assert-Executable -Path $PdsShell -Description 'PDS shell'
Assert-Executable -Path $CompileScript -Description 'compile_simlib Tcl script'

if (-not $SkipSimulatorValidation) {
    Assert-Executable -Path (Join-Path $SimulatorExecPath 'vsim.exe') `
        -Description 'ModelSim/QuestaSim vsim.exe'
    Assert-Executable -Path (Join-Path $SimulatorExecPath 'vlog.exe') `
        -Description 'ModelSim/QuestaSim vlog.exe'
    Assert-Executable -Path (Join-Path $SimulatorExecPath 'vlib.exe') `
        -Description 'ModelSim/QuestaSim vlib.exe'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory, $WorkDirectory, $LogDirectory |
    Out-Null
$LogFile = Join-Path $LogDirectory 'compile-simlib.log'

$PreviousEnvironment = @{
    PDS_SIMULATOR = $env:PDS_SIMULATOR
    PDS_FAMILY = $env:PDS_FAMILY
    PDS_LANGUAGE = $env:PDS_LANGUAGE
    PDS_LIBRARY = $env:PDS_LIBRARY
    PDS_SIMULATOR_EXEC_PATH = $env:PDS_SIMULATOR_EXEC_PATH
    PDS_SIMLIB_DIR = $env:PDS_SIMLIB_DIR
}

try {
    $env:PDS_SIMULATOR = $Simulator
    $env:PDS_FAMILY = $Family
    $env:PDS_LANGUAGE = $Language
    $env:PDS_LIBRARY = $Library
    $env:PDS_SIMULATOR_EXEC_PATH = $SimulatorExecPath
    $env:PDS_SIMLIB_DIR = $OutputDirectory

    Write-Host "INFO: compiling $Library libraries with $Simulator"
    & $PdsShell `
        -file $CompileScript `
        -work_dir $WorkDirectory `
        -project_name simlib `
        2>&1 | Tee-Object -FilePath $LogFile

    if ($LASTEXITCODE -ne 0) {
        throw "PDS compile_simlib failed with exit code $LASTEXITCODE. See $LogFile"
    }
    if (Select-String -LiteralPath $LogFile -Pattern '(?m)^E:' -Quiet) {
        throw "PDS compile_simlib reported an error record. See $LogFile"
    }

    foreach ($LibraryDirectory in @('usim', 'vsim')) {
        if (($Library -eq 'BOTH') -or ($Library -eq $LibraryDirectory.ToUpperInvariant())) {
            Assert-Directory -Path (Join-Path $OutputDirectory $LibraryDirectory) `
                -Description "$LibraryDirectory simulation library"
        }
    }
    Write-Host "INFO: simulation libraries written to $OutputDirectory"
}
finally {
    foreach ($Name in $PreviousEnvironment.Keys) {
        $PreviousValue = $PreviousEnvironment[$Name]
        if ($null -eq $PreviousValue) {
            Remove-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
        } else {
            Set-Item -Path "Env:$Name" -Value $PreviousValue
        }
    }
}
