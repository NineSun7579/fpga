param()

# Validate the S2-B real RC/EP simulation entry without requiring a simulator.
# Dynamic link training remains authoritative only after the Questa run passes.
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

$LinkListPath = Join-Path $ProjectRoot 'sim\link.f'
$VendorListPath = Join-Path $ProjectRoot 'sim\link_vendor_local.f'
$VendorSourceListPath = Join-Path $ProjectRoot `
    'ipcore\pcie_test\sim\modelsim\pango_pcie_top_filelist.f'
$VendorSourceDoPath = Join-Path $ProjectRoot `
    'ipcore\pcie_test\sim\modelsim\pango_pcie_top_sim.do'
$CompileDoPath = Join-Path $PSScriptRoot 'compile_vendor_link.do'
$RunDoPath = Join-Path $PSScriptRoot 'run_link.do'
$RunPath = Join-Path $PSScriptRoot 'run.ps1'
$TestbenchPath = Join-Path $ProjectRoot 'tb\tb_pcie_dma_link.sv'

$RequiredFiles = [ordered]@{
    $LinkListPath = 'PCIe S2-B filelist'
    $VendorListPath = 'PCIe approved vendor-local source list'
    $VendorSourceListPath = 'vendor PCIe source filelist'
    $VendorSourceDoPath = 'vendor PCIe ModelSim DO'
    $CompileDoPath = 'PCIe vendor model compiler'
    $RunDoPath = 'PCIe S2-B simulation DO'
    $RunPath = 'PCIe PowerShell entry'
    $TestbenchPath = 'PCIe S2-B testbench'
}

$AllFilesExist = $true
foreach ($Entry in $RequiredFiles.GetEnumerator()) {
    if (-not (Require-File -Path $Entry.Key -Description $Entry.Value)) {
        $AllFilesExist = $false
    }
}
if (-not $AllFilesExist) {
    throw "PCIe S2-B static gate failed:`n - $($Failures -join "`n - ")"
}

$ExpectedLinkEntries = @(
    '+define+IPS2L_PCIE_SPEEDUP_SIM',
    '+define+IPM_HSST_SPEEDUP_SIM',
    '+define+DWC_DISABLE_CDC_METHOD_REPORTING',
    '+incdir+hdl/pcie_dma_ctrl/ips2l_pcie_dma_ram/rtl',
    '+incdir+ipcore/pcie_test/sim/modelsim',
    '-f sim/link_vendor_local.f',
    '-f scripts/pds_sources.f',
    'tb/tb_pcie_dma_link.sv'
)
$LinkEntries = @(Get-FileListEntries -Path $LinkListPath)
if ((Compare-Object $ExpectedLinkEntries $LinkEntries -SyncWindow 0).Count -gt 0) {
    Add-Failure 'PCIe S2-B filelist does not match the approved ordered contract'
}

# Derive the approved 50 local sources from the read-only vendor filelist. This
# keeps vendor order while excluding its TB, EP top, and duplicate example RTL.
$VendorSourceEntries = @(Get-FileListEntries -Path $VendorSourceListPath)
$ApprovedVendorRawEntries = @($VendorSourceEntries | Where-Object {
        $_ -match '^\.\./\.\./rtl/' -or
        $_ -eq '../../pcie_test.v' -or
        $_ -in @(
            '../../example_design/bench/pango_pcie_top_sim.v',
            '../../example_design/bench/ips2l_pcie_wrap_v1_2c_sim.v',
            '../../example_design/rtl/pcie_cfg_ctrl/rtl/pcie_cfg_ctrl.v',
            '../../example_design/rtl/pcie_cfg_ctrl/rtl/pcie_cfg_ctrl_apb.v',
            '../../example_design/rtl/pcie_cfg_ctrl/rtl/pcie_cfg_trans.v'
        )
    })
$VendorSourceDirectory = Split-Path -Parent $VendorSourceListPath
$ProjectPrefix = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
$ExpectedVendorEntries = @($ApprovedVendorRawEntries | ForEach-Object {
        $AbsolutePath = [IO.Path]::GetFullPath((Join-Path $VendorSourceDirectory ($_ -replace '/', '\')))
        if (-not $AbsolutePath.StartsWith($ProjectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            Add-Failure "Vendor source escapes the PCIe project: $_"
            return
        }
        $AbsolutePath.Substring($ProjectPrefix.Length).Replace('\', '/')
    })
$VendorEntries = @(Get-FileListEntries -Path $VendorListPath)
if ($ExpectedVendorEntries.Count -ne 50 -or $VendorEntries.Count -ne 50) {
    Add-Failure "PCIe approved vendor-local source list must contain 50 paths; expected $($ExpectedVendorEntries.Count), found $($VendorEntries.Count)"
}
if ((Compare-Object $ExpectedVendorEntries $VendorEntries -SyncWindow 0).Count -gt 0) {
    Add-Failure 'PCIe approved vendor-local source list drifted from the vendor source order'
}
if (@($VendorEntries | Group-Object -CaseSensitive | Where-Object Count -gt 1).Count -gt 0) {
    Add-Failure 'PCIe approved vendor-local source list contains duplicate paths'
}

foreach ($Entry in $VendorEntries) {
    if ([IO.Path]::IsPathRooted($Entry) -or
        $Entry.Contains('\') -or
        $Entry -match '(^|/)\.\.(/|$)') {
        Add-Failure "PCIe vendor-local source path is not POSIX project-relative: $Entry"
        continue
    }
    Require-File `
        -Path (Join-Path $ProjectRoot ($Entry -replace '/', '\')) `
        -Description "PCIe vendor-local source $Entry" | Out-Null
}

$ForbiddenVendorPaths = @(
    'pango_pcie_top_tb.v',
    'example_design/bench/pango_pcie_top.v',
    'example_design/rtl/uart2apb_32bit',
    'example_design/rtl/pcie_dma_ctrl'
)
foreach ($Forbidden in $ForbiddenVendorPaths) {
    if ($VendorEntries -match [regex]::Escape($Forbidden)) {
        Add-Failure "PCIe vendor-local source list contains forbidden source: $Forbidden"
    }
}

$TestbenchText = Get-Content -Raw -Encoding UTF8 -LiteralPath $TestbenchPath
$CompileDoText = Get-Content -Raw -Encoding UTF8 -LiteralPath $CompileDoPath
$RunDoText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunDoPath
$RunText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunPath
$VendorSourceDoText = Get-Content -Raw -Encoding UTF8 -LiteralPath $VendorSourceDoPath

foreach ($Required in ([ordered]@{
        'vendor RC instance' = '\bpango_pcie_top_sim\s*#\s*\('
        'project Endpoint instance' = '\bpcie_dma_test\s+u_dut\s*\('
        'single global reset primitive' = '\bGTP_GRS\s+grs_inst\s*\('
        'RC TX to EP RX positive lanes' = '(?s)\.rxp\s*\(rc_txp\).*?\.txp\s*\(ep_txp\)'
        'RC TX to EP RX negative lanes' = '(?s)\.rxn\s*\(rc_txn\).*?\.txn\s*\(ep_txn\)'
        'EP TX to RC RX positive lanes' = '(?s)\.rxp\s*\(ep_txp\).*?\.txp\s*\(rc_txp\)'
        'EP TX to RC RX negative lanes' = '(?s)\.rxn\s*\(ep_txn\).*?\.txn\s*\(rc_txn\)'
        'RC SMLH link check' = 'rc_smlh_link_up\s*===\s*1''b1'
        'RC RDLH link check' = 'rc_rdlh_link_up\s*===\s*1''b1'
        'Endpoint SMLH link check' = 'u_dut\.smlh_link_up\s*===\s*1''b1'
        'Endpoint RDLH link check' = 'u_dut\.rdlh_link_up\s*===\s*1''b1'
        'RC LTSSM L0 check' = 'u_rc\.smlh_ltssm_state\s*===\s*LTSSM_L0'
        'Endpoint LTSSM L0 check' = 'u_dut\.smlh_ltssm_state\s*===\s*LTSSM_L0'
        '32-cycle stability window' = 'LINK_STABLE_CYCLES\s*=\s*32'
        '6 ms watchdog' = '#6ms\s*;\s*\r?\n\s*\$fatal'
        'S2-B success marker' = '\$display\("INFO: S2B_REAL_LINK_UP"\)'
        'unique PASS source' = '\$display\("TEST PASS"\)'
        'private hierarchy warning' = 'depends on named internal status nets'
    }).GetEnumerator()) {
    Require-Pattern -Text $TestbenchText -Pattern $Required.Value -Description $Required.Key
}
if ([regex]::Matches($TestbenchText, '\bGTP_GRS\s+grs_inst\s*\(').Count -ne 1) {
    Add-Failure 'PCIe S2-B testbench must instantiate exactly one GTP_GRS'
}
if ([regex]::Matches($TestbenchText, '\$display\("INFO: S2B_REAL_LINK_UP"\)').Count -ne 1 -or
    [regex]::Matches($TestbenchText, '\$display\("TEST PASS"\)').Count -ne 1) {
    Add-Failure 'PCIe S2-B testbench must contain one success marker and one TEST PASS source'
}
if ($TestbenchText -match '\bpcie_test_smoke_model\b|\bpango_pcie_top_tb\b|\bpango_pcie_top\s+u_') {
    Add-Failure 'PCIe S2-B testbench contains an S2-A model or forbidden vendor top'
}

foreach ($Required in ([ordered]@{
        'PDS root parameter' = 'env\(PANGO_PDS_ROOT\)'
        'vendor source DO extraction' = 'pango_pcie_top_sim\.do'
        'unique model block start marker' = 'set start_marker'
        'unique model block end marker' = 'set end_marker'
        'obsolete prefix replacement' = 'set old_prefix'
        'vendor library rewrite' = 'regsub \{\^vlog\[ \\t\]\+\}'
        'model block evaluation' = 'uplevel #0 \$compile_block'
    }).GetEnumerator()) {
    Require-Pattern -Text $CompileDoText -Pattern $Required.Value -Description $Required.Key
}
if ([regex]::Matches($CompileDoText, '(?m)^vlog -sv -work pcie_vendor').Count -ne 10) {
    Add-Failure 'PCIe vendor compiler must compile exactly ten encrypted DWC headers before the model block'
}
if ($CompileDoText -match 'pango_pcie_top_filelist\.f|vlog-link-vendor-local') {
    Add-Failure 'PCIe vendor library must not compile the full vendor local filelist'
}
$ApprovedObsoletePrefix = 'D:/pds2022_sp6_4/PDS_2022.2-SP6.4/ip/system_ip/ips2l_pcie_gen2/ips2l_pcie_gen2_eval/ips2l_pcie_gen2/../../../../../'
$ActiveAbsoluteLines = @($CompileDoText -split '\r?\n' | Where-Object {
        $_ -notmatch '^\s*#' -and
        $_ -match '[A-Za-z]:[/\\]' -and
        $_ -notmatch 'old_prefix|string first'
    })
if ($ActiveAbsoluteLines.Count -gt 0) {
    Add-Failure 'PCIe vendor compiler contains an active absolute Windows path'
}

$StartMarker = 'vlog -sv +define+IPS2L_PCIE_SPEEDUP_SIM +define+DWC_DISABLE_CDC_METHOD_REPORTING -override_timescale 1ns/10ps'
$EndMarker = '-l vlog_gtp.log'
$OldPrefix = $ApprovedObsoletePrefix
if ([regex]::Matches(
        $CompileDoText,
        [regex]::Escape("set start_marker {$StartMarker}")).Count -ne 1 -or
    [regex]::Matches(
        $CompileDoText,
        [regex]::Escape("set end_marker   {$EndMarker}")).Count -ne 1 -or
    [regex]::Matches(
        $CompileDoText,
        [regex]::Escape("set old_prefix {$OldPrefix}")).Count -ne 1) {
    Add-Failure 'PCIe vendor compiler marker or obsolete-prefix contract drifted'
}
if ([regex]::Matches($VendorSourceDoText, [regex]::Escape($StartMarker)).Count -ne 1 -or
    [regex]::Matches($VendorSourceDoText, [regex]::Escape($EndMarker)).Count -ne 1) {
    Add-Failure 'Vendor PCIe model compile block markers are missing or ambiguous'
} else {
    $StartIndex = $VendorSourceDoText.IndexOf($StartMarker)
    $EndIndex = $VendorSourceDoText.IndexOf($EndMarker, $StartIndex) + $EndMarker.Length
    $ModelBlock = $VendorSourceDoText.Substring($StartIndex, $EndIndex - $StartIndex)
    if ([regex]::Matches($ModelBlock, [regex]::Escape($OldPrefix)).Count -ne 216) {
        Add-Failure 'Vendor PCIe model compile block no longer contains 216 approved PDS path references'
    }
}

foreach ($Required in ([ordered]@{
        'DO fail-fast handler' = 'onerror\s*\{'
        'DO stale transcript cleanup' = 'file\s+delete\s+-force\s+build/logs/sim-link\.log'
        'DO run identity' = 'SIM_RUN_ID'
        'DO run-scoped work library' = 'build/sim/link/\$env\(SIM_RUN_ID\)'
        'DO separate vendor library' = 'vmap\s+pcie_vendor\s+\$vendor_dir'
        'DO vendor compiler call' = 'do\s+scripts/compile_vendor_link\.do'
        'DO S2-B filelist compile' = 'vlog\s+-sv\s+-work\s+work\s+-f\s+sim/link\.f'
        'DO vendor library elaboration' = '-L\s+pcie_vendor'
        'DO S2-B testbench elaboration' = 'work\.tb_pcie_dma_link'
        'DO bounded completion' = 'run\s+-all'
    }).GetEnumerator()) {
    Require-Pattern -Text $RunDoText -Pattern $Required.Value -Description $Required.Key
}
if ($RunDoText -match '[A-Za-z]:[/\\]') {
    Add-Failure 'PCIe S2-B DO contains an absolute Windows path'
}

foreach ($Required in ([ordered]@{
        'PowerShell S2-B action' = "'sim-link'"
        'PowerShell PDS root export' = 'PANGO_PDS_ROOT'
        'PowerShell S2-B log binding' = "-LogFileName 'sim-link\.log'"
        'PowerShell S2-B success marker' = "-SuccessMarker 'INFO: S2B_REAL_LINK_UP'"
        'PowerShell unique PASS gate' = 'does not contain exactly one TEST PASS line'
    }).GetEnumerator()) {
    Require-Pattern -Text $RunText -Pattern $Required.Value -Description $Required.Key
}

if ($Failures.Count -gt 0) {
    throw "PCIe S2-B static gate failed:`n - $($Failures -join "`n - ")"
}

Write-Host 'INFO: PCIe S2-B static simulation gate passed; dynamic link training was not executed'
