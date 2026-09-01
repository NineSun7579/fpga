param()

# Verify the archived post-PNR timing smoke contract without running Questa.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)

    $Failures.Add($Message)
}

function Get-RequiredText {
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [Parameter(Mandatory)][string]$Description
    )

    $Path = Join-Path $ProjectRoot ($RelativePath -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-Failure "$Description not found: $Path"
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
        Add-Failure $Description
    }
}

$FileList = Get-RequiredText `
    -RelativePath 'sim/questa/post_pnr_timing.f' `
    -Description 'PCIe post-PNR timing filelist'
$DoFile = Get-RequiredText `
    -RelativePath 'sim/questa/run_post_pnr_timing.do' `
    -Description 'PCIe post-PNR timing DO entry'
$Testbench = Get-RequiredText `
    -RelativePath 'sim/questa/tb/tb_pcie_dma_post_pnr_timing.sv' `
    -Description 'PCIe post-PNR timing testbench'
$RunScript = Get-RequiredText `
    -RelativePath 'scripts/run_post_pnr_timing_sim.ps1' `
    -Description 'PCIe S2-F PowerShell entry'

Assert-Contains $FileList `
    '(?m)^build/pds/generate_netlist/pcie_dma_test_sim\.v\s*$' `
    'Post-PNR timing filelist does not use the canonical timing netlist'
Assert-Contains $FileList `
    '(?m)^sim/questa/tb/tb_pcie_dma_post_pnr_timing\.sv\s*$' `
    'Post-PNR timing filelist does not use the archived project testbench'

Assert-Contains $DoFile 'SIM_PROJECT_ROOT' `
    'Post-PNR timing DO does not require the project-root contract'
Assert-Contains $DoFile 'SIM_RUN_ID' `
    'Post-PNR timing DO does not bind a simulation run id'
Assert-Contains $DoFile `
    'set\s+run_root\s+\[file normalize "build/sim/post_pnr_timing/\$env\(SIM_RUN_ID\)"\]' `
    'Post-PNR timing DO does not define a run-scoped root'
Assert-Contains $DoFile `
    'set\s+timing_netlist\s+build/pds/generate_netlist/pcie_dma_test_sim\.v' `
    'Post-PNR timing DO does not bind the canonical timing netlist'
Assert-Contains $DoFile `
    'set\s+sdf_file\s+build/pds/generate_netlist/pcie_dma_test_sta\.sdf' `
    'Post-PNR timing DO does not bind the slow-corner SDF'
Assert-Contains $DoFile `
    'string\s+first\s+\{\$sdf_annotate\("pcie_dma_test_sta\.sdf"\)\}' `
    'Post-PNR timing DO does not verify the embedded SDF annotation contract'
Assert-Contains $DoFile `
    'regexp\s+\{.*DESIGN.*pcie_dma_test.*\}' `
    'Post-PNR timing DO does not verify the SDF design name'
Assert-Contains $DoFile `
    'vlog\s+-sv\s+-work\s+work\s+-f\s+sim/questa/post_pnr_timing\.f' `
    'Post-PNR timing DO does not compile the archived filelist'
Assert-Contains $DoFile `
    'cd\s+\$timing_dir' `
    'Post-PNR timing DO does not elaborate from the netlist/SDF directory'
Assert-Contains $DoFile 'work\.tb_pcie_dma_post_pnr_timing' `
    'Post-PNR timing DO does not elaborate the project testbench'
Assert-Contains $DoFile '-suppress\s+2697' `
    'Post-PNR timing elaboration does not suppress the reviewed vendor DRM warning'
Assert-Contains $DoFile '\+delayed_timing_checks' `
    'Post-PNR timing elaboration does not preserve delayed negative timing checks'
Assert-Contains $DoFile '\+ntc_warn' `
    'Post-PNR timing elaboration does not enable negative timing-check diagnostics'
Assert-Contains $DoFile '-glsnegtchk\s+level2' `
    'Post-PNR timing elaboration does not use the Questa LRM negative-check solver'
foreach ($LibraryName in @('usim', 'vsim', 'hsstlp_lane', 'hsstlp_pll', 'pciegen2')) {
    Assert-Contains $DoFile `
        ("vmap\s+{0}\s+" -f $LibraryName) `
        "Post-PNR timing DO does not map $LibraryName"
    Assert-Contains $DoFile `
        ("-L\s+{0}" -f $LibraryName) `
        "Post-PNR timing elaboration does not load $LibraryName"
}
if ($null -ne $DoFile -and $DoFile -match '(?im)-sdf(?:min|max|typ)\b') {
    Add-Failure 'Post-PNR timing DO must not double-annotate the embedded SDF with an external -sdf option'
}
foreach ($DisabledTimingOption in @(
        '\+notimingchecks',
        '\+no_notifier',
        '\+nospecify',
        '\+no_neg_tchk',
        '-glsnegtchk\s+level3'
    )) {
    if ($null -ne $DoFile -and $DoFile -match $DisabledTimingOption) {
        Add-Failure "Post-PNR timing DO contains forbidden timing option '$DisabledTimingOption'"
    }
}

Assert-Contains $Testbench '(?s)@brief.*post-PNR timing' `
    'Post-PNR timing testbench lacks a VSCS responsibility comment'
Assert-Contains $Testbench '(?s)@par Clock and reset contract' `
    'Post-PNR timing testbench lacks its clock/reset contract'
Assert-Contains $Testbench '(?s)Assumption:.*SDF' `
    'Post-PNR timing testbench lacks its SDF assumption'
Assert-Contains $Testbench '(?s)Hazard:.*does not force.*timing' `
    'Post-PNR timing testbench lacks its timing hazard boundary'
Assert-Contains $Testbench `
    '(?s)It does not verify.*PCIe link.*DMA.*release' `
    'Post-PNR timing testbench does not state its exclusions'
Assert-Contains $Testbench 'module\s+tb_pcie_dma_post_pnr_timing\s*;' `
    'Post-PNR timing testbench module is missing'
Assert-Contains $Testbench 'pcie_dma_test\s+dut\s*\(' `
    'Post-PNR timing testbench does not instantiate the project top as dut'
if ($null -ne $Testbench -and $Testbench -match '(?m)^\s*(?:force|release)\s+') {
    Add-Failure 'Post-PNR timing testbench must not force or release mapped design signals'
}
Assert-Contains $Testbench 'repeat\s*\(80\)\s*@\(posedge\s+ref_clk_p\)' `
    'Post-PNR timing testbench does not preserve the natural debounce observation interval'
Assert-Contains $Testbench '#2ms\s*;[\s\r\n]*\$fatal' `
    'Post-PNR timing testbench has no bounded watchdog'
Assert-Contains $Testbench '\$fatal\s*\(' `
    'Post-PNR timing testbench has no hard failure path'
if ($null -ne $Testbench) {
    $PassCount = [regex]::Matches(
        $Testbench,
        '\$display\s*\(\s*"TEST PASS"\s*\)'
    ).Count
    if ($PassCount -ne 1) {
        Add-Failure "Post-PNR timing testbench must contain exactly one TEST PASS display; found $PassCount"
    }
}

Assert-Contains $RunScript 'sim\\questa\\run_post_pnr_timing\.do' `
    'PowerShell S2-F entry does not use the archived DO entry'
Assert-Contains $RunScript 'sim-post-pnr-timing\.log' `
    'PowerShell S2-F entry does not use the fixed log contract'
Assert-Contains $RunScript 'Join-Path\s+\$QuestaBin\s+''win64''' `
    'PowerShell S2-F entry does not accept a Questa installation root'
Assert-Contains $RunScript `
    "'INFO: POST_PNR_TIMING_RESET_PATH_OK'" `
    'PowerShell S2-F entry does not require the functional success marker'
Assert-Contains $RunScript `
    "'SDF Backannotation Successfully Completed'" `
    'PowerShell S2-F entry does not require the simulator SDF success marker'
Assert-Contains $RunScript 'nonzero simulator error summary' `
    'PowerShell S2-F entry does not reject a nonzero simulator error summary'
foreach ($ForbiddenPattern in @(
        'SDF annotation error',
        'Failed to find instance',
        'Timing check violation',
        'Negative timing check',
        '(?m)^#\s+\*\*\s+Error:\s+\$(?:setup|hold|setuphold|recovery|removal|recrem|width|period)\b',
        '\(vsim-8756\)',
        '\(vsim-3004\)'
    )) {
    Assert-Contains $RunScript `
        ([regex]::Escape("'$ForbiddenPattern'")) `
        "PowerShell post-PNR timing action does not reject '$ForbiddenPattern'"
}

if ($Failures.Count -gt 0) {
    Write-Error ("PCIe post-PNR timing simulation gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: PCIe post-PNR timing static simulation gate passed; dynamic simulation was not executed'
exit 0
