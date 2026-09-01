param()

# Validate the S2-A simulation contract without requiring PDS or QuestaSim.
# Dynamic behavior remains authoritative only after the simulator run succeeds.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

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

    if (-not [regex]::IsMatch($Text, $Pattern)) {
        Add-Failure "Missing $Description"
    }
}

function Get-FileListEntries {
    param([Parameter(Mandatory)][string]$Path)

    return @(Get-Content -LiteralPath $Path |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') -and -not $_.StartsWith('//') })
}

$BehaviorListPath = Join-Path $ProjectRoot 'sim\questa\behav.f'
$PdsSourceListPath = Join-Path $PSScriptRoot 'pds_sources.f'
$DoPath = Join-Path $ProjectRoot 'sim\questa\run_behav.do'
$RunPath = Join-Path $PSScriptRoot 'run.ps1'
$CheckPath = $MyInvocation.MyCommand.Path
$TopPath = Join-Path $ProjectRoot 'hdl\pcie_dma_test.v'
$ModelPath = Join-Path $ProjectRoot 'sim\questa\tb\pcie_test_smoke_model.sv'
$TestbenchPath = Join-Path $ProjectRoot 'sim\questa\tb\tb_pcie_dma_test.sv'
$WrapperPath = Join-Path $ProjectRoot 'ipcore\pcie_test\pcie_test.v'

$RequiredFiles = [ordered]@{
    $BehaviorListPath = 'PCIe behavior filelist'
    $PdsSourceListPath = 'PCIe canonical PDS source list'
    $DoPath = 'PCIe behavior DO entry'
    $RunPath = 'PCIe PowerShell entry'
    $CheckPath = 'PCIe simulation static gate'
    $TopPath = 'PCIe project top'
    $ModelPath = 'PCIe controlled smoke model'
    $TestbenchPath = 'PCIe project testbench'
    $WrapperPath = 'active generated PCIe wrapper'
}

$AllFilesExist = $true
foreach ($Entry in $RequiredFiles.GetEnumerator()) {
    if (-not (Require-File -Path $Entry.Key -Description $Entry.Value)) {
        $AllFilesExist = $false
    }
}

if (-not $AllFilesExist) {
    throw "PCIe S2-A static gate failed:`n - $($Failures -join "`n - ")"
}

$ExpectedBehaviorEntries = @(
    '+define+IPS2L_PCIE_SPEEDUP_SIM',
    '+incdir+hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl',
    'ipcore/pcie_test/rtl/hsst_pipe/hsst_rst_cross_sync_v1_0.v',
    'ipcore/pcie_test/rtl/hsst_pipe/hsst_rst_sync_v1_0.v',
    'ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v',
    'sim/questa/tb/pcie_test_smoke_model.sv',
    '-f scripts/pds_sources.f',
    'sim/questa/tb/tb_pcie_dma_test.sv'
)
$BehaviorEntries = @(Get-FileListEntries -Path $BehaviorListPath)
$BehaviorDifference = @(Compare-Object `
    -ReferenceObject $ExpectedBehaviorEntries `
    -DifferenceObject $BehaviorEntries `
    -SyncWindow 0)
if ($BehaviorDifference.Count -gt 0) {
    Add-Failure 'PCIe behavior filelist does not match the approved ordered contract'
}

foreach ($Entry in $BehaviorEntries) {
    if ($Entry -match '^[A-Za-z]:[/\\]' -or $Entry.Contains('\')) {
        Add-Failure "PCIe behavior filelist entry is not POSIX project-relative: $Entry"
    }
    if ($Entry.StartsWith('+incdir+')) {
        $IncludeDirectory = $Entry.Substring('+incdir+'.Length)
        $IncludePath = Join-Path $ProjectRoot ($IncludeDirectory -replace '/', '\')
        if (-not (Test-Path -LiteralPath $IncludePath -PathType Container)) {
            Add-Failure "PCIe simulation include directory not found: $IncludeDirectory"
        } else {
            Write-Host "INFO: found PCIe simulation include directory $IncludeDirectory"
        }
        continue
    }
    if ($Entry.StartsWith('+') -or $Entry.StartsWith('-f ')) {
        continue
    }
    $SourcePath = Join-Path $ProjectRoot ($Entry -replace '/', '\')
    Require-File -Path $SourcePath -Description "PCIe simulation source $Entry" | Out-Null
}

$PdsSourceEntries = @(Get-FileListEntries -Path $PdsSourceListPath)
if ($PdsSourceEntries.Count -ne 37) {
    Add-Failure "PCIe canonical source list must contain 37 paths; found $($PdsSourceEntries.Count)"
}
$PdsDuplicates = @($PdsSourceEntries | Group-Object -CaseSensitive | Where-Object Count -gt 1)
if ($PdsDuplicates.Count -gt 0) {
    Add-Failure 'PCIe canonical source list contains duplicate paths'
}
foreach ($Entry in $PdsSourceEntries) {
    if ([IO.Path]::IsPathRooted($Entry) -or
        $Entry.Contains('\') -or
        $Entry -match '(^|/)\.\.(/|$)') {
        Add-Failure "PCIe canonical source path is not POSIX project-relative: $Entry"
        continue
    }
    Require-File `
        -Path (Join-Path $ProjectRoot ($Entry -replace '/', '\')) `
        -Description "PCIe canonical source $Entry" | Out-Null
}

$TopText = Get-Content -Raw -Encoding UTF8 -LiteralPath $TopPath
$ModelText = Get-Content -Raw -Encoding UTF8 -LiteralPath $ModelPath
$TestbenchText = Get-Content -Raw -Encoding UTF8 -LiteralPath $TestbenchPath
$WrapperText = Get-Content -Raw -Encoding UTF8 -LiteralPath $WrapperPath
$DoText = Get-Content -Raw -Encoding UTF8 -LiteralPath $DoPath
$RunText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunPath

foreach ($Required in ([ordered]@{
        'DMA RX halt top-level declaration' =
            'wire\s*\[2:0\]\s*trgt1_radm_pkt_halt\s*;'
        'DMA RX halt output connection' =
            '\.o_trgt1_radm_pkt_halt\s*\(trgt1_radm_pkt_halt\)'
        'PCIe wrapper RX halt input connection' =
            '\.trgt1_radm_pkt_halt\s*\(trgt1_radm_pkt_halt\)'
        'DMA RX halt backpressure intent' =
            'DMA receive-queue backpressure must reach the PCIe hard IP'
    }).GetEnumerator()) {
    Require-Pattern -Text $TopText -Pattern $Required.Value -Description $Required.Key
}
if ([regex]::Matches(
        $TopText,
        '\.o_trgt1_radm_pkt_halt\s*\(trgt1_radm_pkt_halt\)').Count -ne 1 -or
    [regex]::Matches(
        $TopText,
        '\.trgt1_radm_pkt_halt\s*\(trgt1_radm_pkt_halt\)').Count -ne 1) {
    Add-Failure 'DMA RX halt signal must have exactly one producer and wrapper consumer'
}
foreach ($Required in ([ordered]@{
        'active wrapper RX halt input port' =
            'input\s*\[2:0\]\s*trgt1_radm_pkt_halt\s*,'
        'active wrapper hard-IP halt connection' =
            '\.i_trgt1_radm_pkt_halt\s*\(trgt1_radm_pkt_halt\s*\)'
        'active wrapper regeneration warning' =
            'IP regeneration must preserve this integration port'
    }).GetEnumerator()) {
    Require-Pattern -Text $WrapperText -Pattern $Required.Value -Description $Required.Key
}
if ($WrapperText -match 'assign\s+trgt1_radm_pkt_halt\s*=') {
    Add-Failure 'Active PCIe wrapper still overrides the project RX halt request'
}
if ($ModelText -notmatch 'input\s+wire\s*\[2:0\]\s*trgt1_radm_pkt_halt\s*,') {
    Add-Failure 'PCIe smoke model is missing the RX halt integration input'
}

$TopInstanceMatch = [regex]::Match(
    $TopText,
    '(?s)\bpcie_test\s+u_ips2l_pcie_wrap\s*\((?<body>.*?)\r?\n\);')
if (-not $TopInstanceMatch.Success) {
    Add-Failure 'Unable to locate the pcie_test instance in the project top'
} else {
    $ConnectedPorts = @([regex]::Matches(
            $TopInstanceMatch.Groups['body'].Value,
            '\.(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(') |
        ForEach-Object { $_.Groups['name'].Value } |
        Sort-Object -Unique)
    $DeclaredModelPorts = @([regex]::Matches(
            $ModelText,
            '(?m)^\s*(?:input|output)\s+(?:(?:wire|logic|reg)\s+)?(?:\[[^\]]+\]\s+)?(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*,?\s*$') |
        ForEach-Object { $_.Groups['name'].Value } |
        Sort-Object -Unique)
    $MissingModelPorts = @($ConnectedPorts | Where-Object { $_ -notin $DeclaredModelPorts })
    if ($MissingModelPorts.Count -gt 0) {
        Add-Failure "PCIe smoke model is missing connected ports: $($MissingModelPorts -join ', ')"
    }
}

foreach ($Required in ([ordered]@{
        'controlled pcie_test model module' = '(?m)^module\s+pcie_test\s*\('
        'model scope disclaimer' = 'does not verify LTSSM, TLP, DMA, lane'
        'model reset ownership' = 'assign\s+core_rst_n\s*=\s*button_rst_n\s*&\s*power_up_rst_n\s*&\s*perst_n'
        'model delayed link stimulus' = 'LINK_DELAY_LAST'
        'model always_ff processes' = 'always_ff\s*@\(posedge'
    }).GetEnumerator()) {
    Require-Pattern -Text $ModelText -Pattern $Required.Value -Description $Required.Key
}
if ([regex]::Matches($ModelText, 'always_ff\s*@\(posedge').Count -ne 2) {
    Add-Failure 'PCIe smoke model must contain exactly two always_ff clocked processes'
}
if ($ModelText -match '(?m)^\s*always\s*@') {
    Add-Failure 'PCIe smoke model contains a Verilog always process instead of always_ff'
}

foreach ($Required in ([ordered]@{
        'project testbench module' = '(?m)^module\s+tb_pcie_dma_test\s*;'
        'project top DUT instance' = '\bpcie_dma_test\s+dut\s*\('
        'global reset primitive' = '\bGTP_GRS\s+GRS_INST\s*\('
        'bounded watchdog' = '#3ms\s*;\s*\r?\n\s*\$fatal'
        'reset release check' = 'wait_for_reset_release'
        'minimum debounce assertion' = 'RESET_RELEASE_MINIMUM'
        'button reset interruption' = 'button_rst_n\s*=\s*1''b0'
        'button reset ref-domain preservation' = 'Button reset changed the ref LED counter'
        'PERST reset interruption' = 'perst_n\s*=\s*1''b0'
        'unknown output check' = '\$isunknown'
        'unique PASS source' = '\$display\("TEST PASS"\)'
    }).GetEnumerator()) {
    Require-Pattern -Text $TestbenchText -Pattern $Required.Value -Description $Required.Key
}
if ([regex]::Matches($TestbenchText, '\$display\("TEST PASS"\)').Count -ne 1) {
    Add-Failure 'Project testbench must contain exactly one TEST PASS display'
}
if ([regex]::Matches($TestbenchText, "perst_n\s*=\s*1'b1").Count -ne 2) {
    Add-Failure 'Project testbench must release PERST# once jointly and once independently'
}
if ($TestbenchText -match '\bpango_pcie_top(?:_sim)?\b') {
    Add-Failure 'Project S2-A testbench must not instantiate the vendor RC/EP example'
}

foreach ($Required in ([ordered]@{
        'DO fail-fast handler' = 'onerror\s*\{'
        'DO project-root environment requirement' = 'info exists env\(SIM_PROJECT_ROOT\)'
        'DO project-root discovery' = 'set\s+project_root\s+\[file normalize \$env\(SIM_PROJECT_ROOT\)\]'
        'DO project-root working directory' = 'cd\s+\$project_root'
        'DO stale transcript cleanup' = 'file\s+delete\s+-force\s+build/logs/sim-behav\.log'
        'DO transcript path' = 'transcript\s+file\s+build/logs/sim-behav\.log'
        'DO transcript run identity' = 'echo\s+"INFO:\s+SIM_RUN_ID=\$env\(SIM_RUN_ID\)"'
        'DO run-scoped work library' = 'set\s+work_dir\s+"build/sim/behav/\$env\(SIM_RUN_ID\)/work"'
        'DO shared USIM mapping' = 'vmap\s+usim\s+\.\./build/simlib/usim'
        'DO behavior filelist compile' = 'vlog\s+-sv\s+-work\s+work\s+-f\s+sim/questa/behav\.f'
        'DO project testbench elaboration' = 'work\.tb_pcie_dma_test'
        'DO bounded completion' = 'run\s+-all'
    }).GetEnumerator()) {
    Require-Pattern -Text $DoText -Pattern $Required.Value -Description $Required.Key
}
if ($DoText -match '[A-Za-z]:[/\\]') {
    Add-Failure 'PCIe behavior DO contains an absolute Windows path'
}

foreach ($Required in ([ordered]@{
        'PowerShell behavior action' = "'sim-behav'"
        'PowerShell simulation run identity' = 'SIM_RUN_ID'
        'PowerShell project-root export' = '\$env:SIM_PROJECT_ROOT\s*=\s*\$ProjectRoot'
        'PowerShell project-root restore' = '\$env:SIM_PROJECT_ROOT\s*=\s*\$PreviousSimProjectRoot'
        'PowerShell build-scoped launcher directory' = '\$LaunchDir\s*=\s*Join-Path\s+\$BuildRoot\s+"sim\\launcher\\\$RunId"'
        'PowerShell launcher working directory' = 'Push-Location\s+\$LaunchDir'
        'PowerShell run-scoped modelsim.ini' = '\$ModelsimIni\s*=\s*Join-Path\s+\$LaunchDir\s+''modelsim\.ini'''
        'PowerShell explicit modelsim.ini binding' = '&\s+\$Vsim\s+-c\s+-modelsimini\s+\$ModelsimIni'
        'PowerShell unique PASS gate' = 'does not contain exactly one TEST PASS line'
        'PowerShell behavior log binding' = "-LogFileName 'sim-behav\.log'"
    }).GetEnumerator()) {
    Require-Pattern -Text $RunText -Pattern $Required.Value -Description $Required.Key
}

if ($Failures.Count -gt 0) {
    throw "PCIe S2-A static gate failed:`n - $($Failures -join "`n - ")"
}

Write-Host 'INFO: PCIe S2-A static simulation gate passed'
