param()

# Verify the archived post-PNR functional smoke contract without running Questa.
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
    -RelativePath 'sim/questa/post_pnr_func.f' `
    -Description 'PCIe post-PNR functional filelist'
$DoFile = Get-RequiredText `
    -RelativePath 'sim/questa/run_post_pnr_func.do' `
    -Description 'PCIe post-PNR functional DO entry'
$Testbench = Get-RequiredText `
    -RelativePath 'sim/questa/tb/tb_pcie_dma_post_pnr_func.sv' `
    -Description 'PCIe post-PNR functional testbench'
$RunScript = Get-RequiredText `
    -RelativePath 'scripts/run.ps1' `
    -Description 'PCIe PowerShell entry'
$BuildScript = Get-RequiredText `
    -RelativePath 'scripts/build.tcl' `
    -Description 'PCIe canonical PDS build entry'
$ProvenanceScript = Get-RequiredText `
    -RelativePath 'scripts/build_provenance.ps1' `
    -Description 'PCIe PDS provenance helper'
$BuildGate = Get-RequiredText `
    -RelativePath 'scripts/check_build.ps1' `
    -Description 'PCIe PDS build gate'

Assert-Contains $FileList `
    '(?m)^build/pds/generate_netlist/pcie_dma_test_func\.v\s*$' `
    'Post-PNR functional filelist does not use the stable functional netlist'
Assert-Contains $FileList `
    '(?m)^sim/questa/tb/tb_pcie_dma_post_pnr_func\.sv\s*$' `
    'Post-PNR functional filelist does not use the archived project testbench'

Assert-Contains $DoFile 'SIM_PROJECT_ROOT' `
    'Post-PNR functional DO does not require the project-root contract'
Assert-Contains $DoFile 'SIM_RUN_ID' `
    'Post-PNR functional DO does not bind a simulation run id'
Assert-Contains $DoFile `
    'set\s+run_root\s+\[file normalize "build/sim/post_pnr_func/\$env\(SIM_RUN_ID\)"\]' `
    'Post-PNR functional DO does not define a run-scoped root'
Assert-Contains $DoFile 'vmap\s+usim\s+\.\./build/simlib/usim' `
    'Post-PNR functional DO does not map USIM'
Assert-Contains $DoFile 'vmap\s+vsim\s+\.\./build/simlib/vsim' `
    'Post-PNR functional DO does not map VSIM'
foreach ($LibraryName in @('hsstlp_lane', 'hsstlp_pll', 'pciegen2')) {
    Assert-Contains $DoFile `
        ("vmap\s+{0}\s+\.\./build/simlib/{0}" -f $LibraryName) `
        "Post-PNR functional DO does not map $LibraryName"
    Assert-Contains $DoFile `
        ("-L\s+{0}" -f $LibraryName) `
        "Post-PNR functional elaboration does not load $LibraryName"
}
Assert-Contains $DoFile `
    'vlog\s+-sv\s+-work\s+work\s+-f\s+sim/questa/post_pnr_func\.f' `
    'Post-PNR functional DO does not compile the archived filelist'
Assert-Contains $DoFile '-L\s+vsim' `
    'Post-PNR functional elaboration does not load VSIM'
Assert-Contains $DoFile `
    'set\s+functional_netlist\s+build/pds/generate_netlist/pcie_dma_test_func\.v' `
    'Post-PNR functional DO does not use the stable functional netlist'
Assert-Contains $DoFile `
    'while\s+\{\[gets\s+\$netlist_handle\s+netlist_line\]\s+>=\s+0\}' `
    'Post-PNR functional DO does not scan the functional netlist without loading it into the transcript'
Assert-Contains $DoFile `
    'string\s+first\s+\{\$sdf_annotate\}\s+\$netlist_line' `
    'Post-PNR functional DO does not reject embedded SDF annotation'
Assert-Contains $DoFile '-suppress\s+2697' `
    'Post-PNR functional elaboration does not suppress the reviewed repetitive vendor DRM warning'
if ($null -ne $DoFile -and $DoFile -match 'set\s+\S+\s+\[read\s+\$netlist_handle\]') {
    Add-Failure 'Post-PNR functional DO must not echo the complete netlist into the transcript'
}
Assert-Contains $DoFile 'work\.tb_pcie_dma_post_pnr_func' `
    'Post-PNR functional DO does not elaborate the project testbench'
if ($null -ne $DoFile -and
    $DoFile -match '(?im)(?:-sdf(?:min|max|typ)\b|\$sdf_annotate\s*\()') {
    Add-Failure 'Post-PNR functional DO must not annotate SDF'
}

Assert-Contains $Testbench '(?s)@brief.*post-PNR functional' `
    'Post-PNR functional testbench lacks a VSCS responsibility comment'
Assert-Contains $Testbench `
    '(?s)It does not verify.*PCIe link.*DMA.*timing' `
    'Post-PNR functional testbench does not state its exclusions'
Assert-Contains $Testbench 'module\s+tb_pcie_dma_post_pnr_func\s*;' `
    'Post-PNR functional testbench module is missing'
Assert-Contains $Testbench 'pcie_dma_test\s+dut\s*\(' `
    'Post-PNR functional testbench does not instantiate the project top'
Assert-Contains $Testbench 'force\s+dut\.smlh_link_up\s*=\s*1''b1' `
    'Post-PNR functional testbench does not control the preserved link net'
Assert-Contains $Testbench 'force\s+dut\.rdlh_link_up\s*=\s*1''b1' `
    'Post-PNR functional testbench does not control both preserved link nets'
Assert-Contains $Testbench '\$fatal\s*\(' `
    'Post-PNR functional testbench has no hard failure path'
Assert-Contains $Testbench '#2ms\s*;[\s\r\n]*\$fatal' `
    'Post-PNR functional testbench has no bounded watchdog'
if ($null -ne $Testbench) {
    $PassCount = [regex]::Matches(
        $Testbench,
        '\$display\s*\(\s*"TEST PASS"\s*\)'
    ).Count
    if ($PassCount -ne 1) {
        Add-Failure "Post-PNR functional testbench must contain exactly one TEST PASS display; found $PassCount"
    }
}

Assert-Contains $RunScript `
    "-DoFileName\s+'sim/questa/run_post_pnr_func\.do'" `
    'PowerShell post-PNR functional action does not use the archived DO entry'
Assert-Contains $RunScript `
    "-LogFileName\s+'sim-post-pnr-func\.log'" `
    'PowerShell post-PNR functional action does not use the fixed log contract'
Assert-Contains $RunScript `
    "-SuccessMarker\s+'INFO: POST_PNR_FUNC_RESET_PATH_OK'" `
    'PowerShell post-PNR functional action does not require the success marker'

Assert-Contains $BuildScript `
    'gen_netlist\s+\\\s*-sdf_annotate\s+TRUE' `
    'Canonical PDS build no longer preserves the timing netlist and SDF flow'
Assert-Contains $RunScript 'function\s+Invoke-PdsFunctionalNetlist' `
    'PowerShell build entry does not define isolated functional-netlist generation'
Assert-Contains $RunScript `
    'Join-Path\s+\$BuildRoot\s+"pds-func-\$RunId"' `
    'PowerShell build entry does not keep the copied PDS project at canonical directory depth'
Assert-Contains $RunScript `
    "'\(_option sdf_annotate \(_boolean TRUE\)\)'" `
    'PowerShell build entry does not require the canonical timing-netlist option'
Assert-Contains $RunScript `
    "'\(_option func_sim_only \(_switch ON\)\)'" `
    'PowerShell build entry does not enable functional-netlist mode in the copied project'
Assert-Contains $RunScript `
    '\(_option sdf_annotate \(_boolean FALSE\)\)' `
    'PowerShell build entry does not disable SDF annotation in the copied project'
Assert-Contains $RunScript `
    '-project\s+\$FunctionalProject\s+`?\s*-run\s+gen_netlist' `
    'PowerShell build entry does not run functional netlist generation in a separate PDS process'
Assert-Contains $RunScript `
    "'generate_netlist\\pcie_dma_test_func\.v'" `
    'PowerShell build entry does not archive the stable functional netlist'
Assert-Contains $RunScript `
    '-SimpleMatch\s+''\$sdf_annotate''' `
    'PowerShell build entry does not reject embedded SDF annotation'
Assert-Contains $RunScript `
    'Invoke-PdsFunctionalNetlist\s+-RunId\s+\$RunId' `
    'Complete PDS build does not invoke isolated functional-netlist generation'
Assert-Contains $ProvenanceScript `
    "'build/pds/generate_netlist/pcie_dma_test_func\.v'" `
    'PDS provenance does not bind the functional netlist artifact'
Assert-Contains $ProvenanceScript `
    "'build/logs/pds-post-pnr-func-netlist\.log'" `
    'PDS provenance does not bind the functional-netlist generation log'
Assert-Contains $BuildGate `
    "'generate_netlist\\pcie_dma_test_func\.v'" `
    'PDS build gate does not require the functional netlist'
Assert-Contains $BuildGate `
    '-SimpleMatch\s+''\$sdf_annotate''' `
    'PDS build gate does not reject SDF annotation in the functional netlist'

if ($Failures.Count -gt 0) {
    Write-Error ("PCIe post-PNR functional simulation gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: PCIe post-PNR functional static simulation gate passed; dynamic simulation was not executed'
exit 0
