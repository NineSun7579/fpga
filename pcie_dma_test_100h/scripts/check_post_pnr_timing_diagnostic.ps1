param()

# Verify that the diagnostic matrix changes only the Questa solver level and
# remains structurally separate from the canonical S2-F acceptance entry.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

function Get-RequiredText {
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [Parameter(Mandatory)][string]$Description
    )

    $Path = Join-Path $ProjectRoot ($RelativePath -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Failures.Add("$Description not found: $Path")
        return $null
    }
    Write-Host "INFO: found $Description"
    return Get-Content -Raw -LiteralPath $Path
}

function Assert-Contains {
    param(
        [AllowNull()][string]$Text,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][string]$Description
    )

    if ($null -ne $Text -and $Text -notmatch $Pattern) {
        $Failures.Add($Description)
    }
}

$DiagnosticDo = Get-RequiredText `
    -RelativePath 'sim/questa/run_post_pnr_timing_diagnostic.do' `
    -Description 'S2-F negative-timing diagnostic DO entry'
$DiagnosticRunner = Get-RequiredText `
    -RelativePath 'scripts/run_post_pnr_timing_diagnostic.ps1' `
    -Description 'S2-F negative-timing diagnostic PowerShell entry'
$CanonicalDo = Get-RequiredText `
    -RelativePath 'sim/questa/run_post_pnr_timing.do' `
    -Description 'canonical S2-F DO entry'

foreach ($Contract in @(
        [pscustomobject]@{
            Pattern = 'set\s+timing_netlist\s+build/pds/generate_netlist/pcie_dma_test_sim\.v'
            Description = 'Diagnostic DO does not bind the canonical timing netlist'
        },
        [pscustomobject]@{
            Pattern = 'set\s+sdf_file\s+build/pds/generate_netlist/pcie_dma_test_sta\.sdf'
            Description = 'Diagnostic DO does not bind the canonical slow-corner SDF'
        },
        [pscustomobject]@{
            Pattern = 'vlog\s+-sv\s+-work\s+work\s+-f\s+sim/questa/post_pnr_timing\.f'
            Description = 'Diagnostic DO does not compile the canonical timing filelist'
        },
        [pscustomobject]@{
            Pattern = 'SIM_GLS_NEG_TCHK_LEVEL'
            Description = 'Diagnostic DO does not require an explicit solver level'
        },
        [pscustomobject]@{
            Pattern = '-glsnegtchk\s+\$solver_level'
            Description = 'Diagnostic DO does not vary only the solver level'
        },
        [pscustomobject]@{
            Pattern = '\+delayed_timing_checks'
            Description = 'Diagnostic DO does not retain delayed timing checks'
        },
        [pscustomobject]@{
            Pattern = '\+ntc_warn'
            Description = 'Diagnostic DO does not retain negative-check diagnostics'
        },
        [pscustomobject]@{
            Pattern = 'DIAGNOSTIC_ONLY=S2F_ACCEPTANCE_UNCHANGED'
            Description = 'Diagnostic DO does not mark the result as non-acceptance evidence'
        }
    )) {
    Assert-Contains $DiagnosticDo $Contract.Pattern $Contract.Description
}

foreach ($LibraryName in @('usim', 'vsim', 'hsstlp_lane', 'hsstlp_pll', 'pciegen2')) {
    Assert-Contains $DiagnosticDo ("vmap\s+{0}\s+" -f $LibraryName) `
        "Diagnostic DO does not map $LibraryName"
    Assert-Contains $DiagnosticDo ("-L\s+{0}" -f $LibraryName) `
        "Diagnostic DO does not load $LibraryName"
}

foreach ($ForbiddenOption in @(
        '\+notimingchecks',
        '\+no_notifier',
        '\+nospecify',
        '\+no_neg_tchk',
        '-glsnegtchk\s+level0',
        '(?im)-sdf(?:min|max|typ)\b'
    )) {
    if ($null -ne $DiagnosticDo -and $DiagnosticDo -match $ForbiddenOption) {
        $Failures.Add("Diagnostic DO contains forbidden option '$ForbiddenOption'")
    }
}

Assert-Contains $DiagnosticRunner "@\('level1',\s*'level2',\s*'level3'\)" `
    'Diagnostic runner does not parse the exact three solver levels'
Assert-Contains $DiagnosticRunner 'VsimProcessExitCode' `
    'Diagnostic runner does not record each simulator process exit code'
Assert-Contains $DiagnosticRunner '\[IO\.Directory\]::Delete\(\$RuntimeDirectory,\s*\$true\)' `
    'Diagnostic runner does not bound disk usage by removing run-scoped work directories'
Assert-Contains $DiagnosticRunner 'Refusing to manage a diagnostic path outside its run root' `
    'Diagnostic runner does not validate cleanup paths before recursive deletion'
Assert-Contains $DiagnosticRunner '\[string\]\$PdsRoot' `
    'Diagnostic runner does not require the external PDS installation root'
Assert-Contains $DiagnosticRunner 'Get-FileHash\s+-Algorithm\s+SHA256' `
    'Diagnostic runner does not record input and model hashes'
Assert-Contains $DiagnosticRunner 'V_FFASYN\.v' `
    'Diagnostic runner does not hash the V_FFASYN model'
Assert-Contains $DiagnosticRunner 'V_DRM18K_E1\.v' `
    'Diagnostic runner does not hash the V_DRM18K_E1 model'
Assert-Contains $DiagnosticRunner '\$Vsim\s+-version' `
    'Diagnostic runner does not record the Questa version'
Assert-Contains $DiagnosticRunner "AcceptanceStatus\s*=\s*'blocked'" `
    'Diagnostic runner does not preserve the blocked acceptance state'
Assert-Contains $DiagnosticRunner 'CanonicalAcceptanceChanged\s*=\s*\$false' `
    'Diagnostic runner can misrepresent a diagnostic as an acceptance change'
Assert-Contains $DiagnosticRunner 'Vsim3004' `
    'Diagnostic runner does not count unsolved negative limits'
Assert-Contains $DiagnosticRunner 'Vsim8756' `
    'Diagnostic runner does not count incomplete delayed-copy models'
Assert-Contains $DiagnosticRunner 'Vsim3316' `
    'Diagnostic runner does not count aggregate negative-limit failures'
Assert-Contains $DiagnosticRunner 'Vsim3616' `
    'Diagnostic runner does not count negative-check pulse rejection diagnostics'
Assert-Contains $DiagnosticRunner 'SetupErrors' `
    'Diagnostic runner does not count positive setup errors'
Assert-Contains $DiagnosticRunner 'HoldErrors' `
    'Diagnostic runner does not count positive hold errors'
Assert-Contains $DiagnosticRunner 'SimulatorErrors' `
    'Diagnostic runner does not retain the simulator error summary'
Assert-Contains $CanonicalDo '-glsnegtchk\s+level2' `
    'Canonical S2-F entry no longer uses the LRM-compliant level2 solver'

if ($Failures.Count -gt 0) {
    Write-Error ("PCIe S2-F diagnostic gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: PCIe S2-F diagnostic gate passed; dynamic matrix was not executed'
exit 0
