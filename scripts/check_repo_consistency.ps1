param(
    [string]$RepoRoot
)

# Perform the repository-level checks that do not require PDS or a simulator.
# This is a structural gate, not a replacement for project build gates.
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

$Failures = [System.Collections.Generic.List[string]]::new()
$MatrixPath = Join-Path $RepoRoot 'docs\SIMULATION_READINESS_MATRIX.md'

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)
    $Failures.Add($Message)
}

function Require-File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-Failure "$Description not found: $Path"
        return $false
    }

    Write-Host "INFO: found $Description"
    return $true
}

function Require-Pattern {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][string]$Description
    )

    if ($Text -notmatch $Pattern) {
        Add-Failure "Missing $Description"
        return $false
    }

    return $true
}

$Projects = @(
    [pscustomobject]@{
        Name = 'OV7725 HDMI'
        Root = '41_ov7725_hdmi'
        Top = 'ov7725_hdmi'
        Readme = 'README.md'
    },
    [pscustomobject]@{
        Name = 'DDR3 bring-up'
        Root = 'ddr3_test/ddr3_test'
        Top = 'test_ddr'
        Readme = 'README.md'
    },
    [pscustomobject]@{
        Name = 'PCIe DMA'
        Root = 'pcie_dma_test_100h'
        Top = 'pcie_dma_test'
        Readme = 'README.md'
    }
)

Write-Host "INFO: checking repository root $RepoRoot"
Require-File -Path (Join-Path $RepoRoot 'README.md') -Description 'root guide' | Out-Null
Require-File -Path (Join-Path $RepoRoot 'TODO.md') -Description 'root TODO' | Out-Null
Require-File -Path (Join-Path $RepoRoot 'VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md') `
    -Description 'Verilog/SystemVerilog commenting standard' | Out-Null

$SimlibTclPath = Join-Path $RepoRoot 'scripts\compile_simlib.tcl'
$SimlibPsPath = Join-Path $RepoRoot 'scripts\compile_simlib.ps1'
$SimlibTclExists = Require-File -Path $SimlibTclPath `
    -Description 'compile_simlib Tcl entry'
$SimlibPsExists = Require-File -Path $SimlibPsPath `
    -Description 'compile_simlib PowerShell entry'
if ($SimlibTclExists) {
    $SimlibTclText = Get-Content -Raw -Encoding UTF8 -LiteralPath $SimlibTclPath
    Require-Pattern -Text $SimlibTclText -Pattern '(?m)\bcompile_simlib\b' `
        -Description 'PDS compile_simlib command' | Out-Null
    Require-Pattern -Text $SimlibTclText -Pattern 'PDS_SIMULATOR_EXEC_PATH' `
        -Description 'external simulator path parameter' | Out-Null
}
if ($SimlibPsExists) {
    $SimlibPsText = Get-Content -Raw -Encoding UTF8 -LiteralPath $SimlibPsPath
    Require-Pattern -Text $SimlibPsText -Pattern '\$LASTEXITCODE' `
        -Description 'compile_simlib exit-code check' | Out-Null
    Require-Pattern -Text $SimlibPsText -Pattern 'vsim\.exe' `
        -Description 'mandatory simulator preflight' | Out-Null
}

$RootReadmePath = Join-Path $RepoRoot 'README.md'
$TodoPath = Join-Path $RepoRoot 'TODO.md'
$MatrixExists = Require-File -Path $MatrixPath -Description 'simulation readiness matrix'
if ($MatrixExists) {
    $MatrixText = Get-Content -Raw -Encoding UTF8 -LiteralPath $MatrixPath
    Require-Pattern -Text $MatrixText -Pattern 'OV7725 HDMI' `
        -Description 'simulation matrix OV7725 coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'DDR3' `
        -Description 'simulation matrix DDR3 coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'PCIe DMA' `
        -Description 'simulation matrix PCIe coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S1 DDR3|S2 PCIe|S3 OV7725' `
        -Description 'simulation matrix execution queue' | Out-Null
}

if (Test-Path -LiteralPath $RootReadmePath -PathType Leaf) {
    $RootReadmeText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RootReadmePath
    Require-Pattern -Text $RootReadmeText `
        -Pattern 'docs/SIMULATION_READINESS_MATRIX\.md' `
        -Description 'root guide simulation matrix link' | Out-Null
}
if (Test-Path -LiteralPath $TodoPath -PathType Leaf) {
    $TodoText = Get-Content -Raw -Encoding UTF8 -LiteralPath $TodoPath
    Require-Pattern -Text $TodoText `
        -Pattern 'docs/SIMULATION_READINESS_MATRIX\.md' `
        -Description 'TODO simulation matrix link' | Out-Null
}

$IgnoreText = Get-Content -Raw -LiteralPath (Join-Path $RepoRoot '.gitignore')
Require-Pattern -Text $IgnoreText -Pattern '(?m)^build/$' `
    -Description 'build/ ignore rule' | Out-Null

$TrackedBuild = @(git -C $RepoRoot ls-files -- '*build*' | Where-Object {
        $_ -match '(^|/)build/'
    })
if ($TrackedBuild.Count -gt 0) {
    Add-Failure "Generated build files are tracked: $($TrackedBuild -join ', ')"
} else {
    Write-Host 'INFO: no generated build files are tracked'
}

foreach ($Project in $Projects) {
    $ProjectRoot = Join-Path $RepoRoot ($Project.Root -replace '/', '\')
    Write-Host "INFO: checking $($Project.Name)"

    $ReadmePath = Join-Path $ProjectRoot $Project.Readme
    $BuildPath = Join-Path $ProjectRoot 'scripts\build.tcl'
    $RunPath = Join-Path $ProjectRoot 'scripts\run.ps1'
    $GatePath = Join-Path $ProjectRoot 'scripts\check_build.ps1'

    $ReadmeExists = Require-File -Path $ReadmePath -Description "$($Project.Name) README"
    $BuildExists = Require-File -Path $BuildPath -Description "$($Project.Name) build.tcl"
    $RunExists = Require-File -Path $RunPath -Description "$($Project.Name) run.ps1"
    $GateExists = Require-File -Path $GatePath -Description "$($Project.Name) check_build.ps1"

    if ($ReadmeExists) {
        $ReadmeText = Get-Content -Raw -Encoding UTF8 -LiteralPath $ReadmePath
        $TopPattern = [regex]::Escape($Project.Top)
        Require-Pattern -Text $ReadmeText -Pattern '2022\.2-SP6\.4' `
            -Description "$($Project.Name) PDS version in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $TopPattern `
            -Description "$($Project.Name) top module in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern '(?i)仿真|ModelSim|QuestaSim' `
            -Description "$($Project.Name) simulation status in README" | Out-Null
    }

    if ($BuildExists) {
        $BuildText = Get-Content -Raw -Encoding UTF8 -LiteralPath $BuildPath
        $TopModulePattern = [regex]::Escape("-top_module $($Project.Top)")
        Require-Pattern -Text $BuildText -Pattern 'file\s+normalize' `
            -Description "$($Project.Name) normalized project path" | Out-Null
        Require-Pattern -Text $BuildText -Pattern '(?m)\bset_arch\b' `
            -Description "$($Project.Name) device declaration" | Out-Null
        Require-Pattern -Text $BuildText -Pattern $TopModulePattern `
            -Description "$($Project.Name) top module declaration" | Out-Null

        foreach ($Stage in @('compile', 'synthesize', 'dev_map', 'pnr', 'report_timing', 'gen_netlist', 'gen_bit_stream')) {
            Require-Pattern -Text $BuildText -Pattern "(?m)\b$Stage\b" `
                -Description "$($Project.Name) $Stage stage" | Out-Null
        }

        if ($BuildText -match '(?m)^\s*simulate\b') {
            Add-Failure "$($Project.Name) build.tcl uses unsupported simulate command"
        }
        if ($BuildText -match '(?m)^\s*(?:set|add_design|add_constraint|source)\b[^\r\n]*[A-Za-z]:\\') {
            Add-Failure "$($Project.Name) Tcl contains a backslash absolute path"
        }
    }

    if ($RunExists) {
        $RunText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunPath
        Require-Pattern -Text $RunText -Pattern '\$PdsBin|\$PdsShell' `
            -Description "$($Project.Name) configurable PDS path" | Out-Null
        Require-Pattern -Text $RunText -Pattern '(?i)-file' `
            -Description "$($Project.Name) PDS script invocation" | Out-Null
        Require-Pattern -Text $RunText -Pattern '(?i)-work[_-]dir' `
            -Description "$($Project.Name) isolated work directory" | Out-Null
        Require-Pattern -Text $RunText -Pattern '\$LASTEXITCODE' `
            -Description "$($Project.Name) process exit-code check" | Out-Null
    }

    if ($GateExists) {
        $GateText = Get-Content -Raw -Encoding UTF8 -LiteralPath $GatePath
        Require-Pattern -Text $GateText -Pattern 'AllowKnownBaselineIssues' `
            -Description "$($Project.Name) explicit baseline switch" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)Test-Path|Assert-NonEmptyFile' `
            -Description "$($Project.Name) artifact existence check" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)Timing|WNS|TNS|Constraints Met' `
            -Description "$($Project.Name) timing gate" | Out-Null
    }
}

if ($Failures.Count -gt 0) {
    Write-Error ("Repository consistency gate failed with {0} issue(s):`n- {1}" -f `
        $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: repository consistency gate passed'
exit 0
