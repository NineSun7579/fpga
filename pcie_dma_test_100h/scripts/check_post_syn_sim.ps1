param()

# Verify the archived post-synthesis smoke contract without running Questa.
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
    -RelativePath 'sim/questa/post_syn.f' `
    -Description 'PCIe post-synthesis filelist'
$DoFile = Get-RequiredText `
    -RelativePath 'sim/questa/run_post_syn.do' `
    -Description 'PCIe post-synthesis DO entry'
$Testbench = Get-RequiredText `
    -RelativePath 'sim/questa/tb/tb_pcie_dma_post_syn.sv' `
    -Description 'PCIe post-synthesis testbench'
$RunScript = Get-RequiredText `
    -RelativePath 'scripts/run.ps1' `
    -Description 'PCIe PowerShell entry'

Assert-Contains $FileList `
    '(?m)^build/pds/synthesize/pcie_dma_test_syn\.vm\s*$' `
    'Post-synthesis filelist does not use the canonical PDS synthesis netlist'
Assert-Contains $FileList `
    '(?m)^sim/questa/tb/tb_pcie_dma_post_syn\.sv\s*$' `
    'Post-synthesis filelist does not use the archived project testbench'

Assert-Contains $DoFile `
    'SIM_PROJECT_ROOT' `
    'Post-synthesis DO does not require the project-root runtime contract'
Assert-Contains $DoFile `
    'SIM_RUN_ID' `
    'Post-synthesis DO does not bind a simulation run id'
Assert-Contains $DoFile `
    'PANGO_PDS_ROOT' `
    'Post-synthesis DO does not require the installed PCIe model root'
Assert-Contains $DoFile `
    'set\s+run_root\s+\[file normalize "build/sim/post_syn/\$env\(SIM_RUN_ID\)"\]' `
    'Post-synthesis DO does not define a run-scoped root'
Assert-Contains $DoFile `
    'set\s+work_dir\s+"\$run_root/work"' `
    'Post-synthesis DO does not derive the work library from the run root'
Assert-Contains $DoFile `
    'set\s+vendor_dir\s+"\$run_root/pcie_vendor"' `
    'Post-synthesis DO does not use a run-scoped PCIe vendor library'
Assert-Contains $DoFile `
    'vmap\s+usim\s+\.\./build/simlib/usim' `
    'Post-synthesis DO does not map the shared USIM library'
Assert-Contains $DoFile `
    'vlog\s+-sv\s+-work\s+work\s+-f\s+sim/questa/post_syn\.f' `
    'Post-synthesis DO does not compile the archived filelist'
Assert-Contains $DoFile `
    'do\s+sim/questa/compile_vendor_link\.do' `
    'Post-synthesis DO does not reuse the approved PCIe vendor model compiler'
Assert-Contains $DoFile `
    '-L\s+usim' `
    'Post-synthesis elaboration does not load USIM'
Assert-Contains $DoFile `
    '-L\s+pcie_vendor' `
    'Post-synthesis elaboration does not load the PCIe vendor library'
Assert-Contains $DoFile `
    'work\.tb_pcie_dma_post_syn' `
    'Post-synthesis DO does not elaborate the project testbench'

Assert-Contains $Testbench `
    '(?s)@brief.*post-synthesis' `
    'Post-synthesis testbench lacks a VSCS module responsibility comment'
Assert-Contains $Testbench `
    '(?s)It does not verify.*PCIe link.*DMA.*timing' `
    'Post-synthesis testbench does not state its verification exclusions'
Assert-Contains $Testbench `
    'module\s+tb_pcie_dma_post_syn\s*;' `
    'Post-synthesis testbench module is missing'
Assert-Contains $Testbench `
    'pcie_dma_test\s+dut\s*\(' `
    'Post-synthesis testbench does not instantiate the project top'
Assert-Contains $Testbench `
    'GTP_GRS\s+GRS_INST\s*\(' `
    'Post-synthesis testbench does not provide the required global reset model'
Assert-Contains $Testbench `
    'force\s+dut\.smlh_link_up\s*=\s*1''b1' `
    'Post-synthesis testbench does not control the preserved link observation net'
Assert-Contains $Testbench `
    'force\s+dut\.rdlh_link_up\s*=\s*1''b1' `
    'Post-synthesis testbench does not control both preserved link observation nets'
Assert-Contains $Testbench `
    '\$fatal\s*\(' `
    'Post-synthesis testbench has no hard failure path'
Assert-Contains $Testbench `
    '#2ms\s*;[\s\r\n]*\$fatal' `
    'Post-synthesis testbench has no bounded watchdog'
if ($null -ne $Testbench) {
    $PassCount = [regex]::Matches($Testbench, '\$display\s*\(\s*"TEST PASS"\s*\)').Count
    if ($PassCount -ne 1) {
        Add-Failure "Post-synthesis testbench must contain exactly one TEST PASS display; found $PassCount"
    }
}

Assert-Contains $RunScript `
    "-DoFileName\s+'sim/questa/run_post_syn\.do'" `
    'PowerShell post-synthesis action does not use the archived DO entry'
Assert-Contains $RunScript `
    "-LogFileName\s+'sim-post-syn\.log'" `
    'PowerShell post-synthesis action does not use the fixed log contract'
Assert-Contains $RunScript `
    '-PangoPdsRoot\s+\(Split-Path\s+-Parent\s+\$PdsBin\)' `
    'PowerShell post-synthesis action does not pass the installed PDS root'
Assert-Contains $RunScript `
    "-SuccessMarker\s+'INFO: POST_SYN_RESET_PATH_OK'" `
    'PowerShell post-synthesis action does not require the success marker'

if ($Failures.Count -gt 0) {
    Write-Error ("PCIe post-synthesis simulation gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: PCIe post-synthesis static simulation gate passed; dynamic simulation was not executed'
exit 0
