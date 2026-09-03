[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SimulatorExecPath
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$RunRoot = Join-Path $ProjectRoot (Join-Path 'build' (Join-Path 'm3a' $RunId))
$WorkLib = Join-Path $RunRoot 'work'
$LogPath = Join-Path $RunRoot 'run.log'

function Require-Executable {
    param(
        [string]$Name
    )

    $Path = Join-Path $SimulatorExecPath $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required simulator executable not found: $Path"
    }
    return $Path
}

New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$Vlib = Require-Executable 'vlib.exe'
$Vlog = Require-Executable 'vlog.exe'
$Vmap = Require-Executable 'vmap.exe'
$Vsim = Require-Executable 'vsim.exe'

$Sources = @(
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_capture.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_grayscale.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_pipeline.sv'),
    (Join-Path $ProjectRoot 'rtl\rgb565_word_packer.sv'),
    (Join-Path $ProjectRoot 'rtl\ov5640_dvp_rgb565_word_pipeline.sv'),
    (Join-Path $ProjectRoot 'tb\tb_ov5640_dvp_rgb565_word_pipeline.sv')
)

Push-Location $RunRoot
try {
    & $Vlib $WorkLib 2>&1 | Tee-Object -FilePath $LogPath
    if ($LASTEXITCODE -ne 0) {
        throw "vlib.exe failed with exit code $LASTEXITCODE"
    }

    & $Vlog -sv -work $WorkLib $Sources 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "vlog.exe failed with exit code $LASTEXITCODE"
    }

    & $Vmap work $WorkLib 2>&1 | Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        throw "vmap.exe failed with exit code $LASTEXITCODE"
    }

    & $Vsim -c -lib work tb_ov5640_dvp_rgb565_word_pipeline `
        -do 'run -all; quit -f' 2>&1 | Tee-Object -FilePath $LogPath -Append
    $VsimExit = $LASTEXITCODE
    if ($VsimExit -ne 0) {
        exit $VsimExit
    }

    # Questa prefixes transcript lines with "# "; accept that stable wrapper.
    $PassCount = @(Select-String -LiteralPath $LogPath -Pattern '^(?:# )?TEST PASS$').Count
    if ($PassCount -ne 1) {
        throw "Expected exactly one TEST PASS marker, observed $PassCount"
    }
    Write-Output "M3-A PASS: $LogPath"
} finally {
    Pop-Location
}
