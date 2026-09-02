param(
    [string]$RepoRoot,
    [string]$PdsTclInventoryPath,
    [string]$SensitiveDiffBaseRef = 'origin/main'
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
$GithubWorkflowPath = Join-Path $RepoRoot `
    '.github\workflows\repository-gates.yml'
$GithubGateDocPath = Join-Path $RepoRoot 'docs\GITHUB_PR_GATE.md'
$GithubCheckoutSha = '3d3c42e5aac5ba805825da76410c181273ba90b1'
$PdsTclInventoryDocPath = Join-Path $RepoRoot `
    'docs\PDS_TCL_ENTRYPOINT_INVENTORY.md'
if ([string]::IsNullOrWhiteSpace($PdsTclInventoryPath)) {
    $PdsTclInventoryPath = Join-Path $RepoRoot `
        'docs\PDS_TCL_ENTRYPOINT_INVENTORY.json'
}
$PdsTclGatePath = Join-Path $RepoRoot 'scripts\check_pds_tcl_entrypoints.ps1'
$SensitiveDiffGatePath = Join-Path $RepoRoot 'scripts\check_sensitive_diff.ps1'
$SensitiveDiffGateDocPath = Join-Path $RepoRoot 'docs\SENSITIVE_DIFF_GATE.md'
$ConstraintExceptionGatePath = Join-Path $RepoRoot `
    'scripts\check_constraint_exceptions.ps1'
$ConstraintExceptionInventoryPath = Join-Path $RepoRoot `
    'docs\CONSTRAINT_EXCEPTION_INVENTORY.json'
$ConstraintExceptionInventoryDocPath = Join-Path $RepoRoot `
    'docs\CONSTRAINT_EXCEPTION_INVENTORY.md'
$GitAttributesPath = Join-Path $RepoRoot '.gitattributes'
$Ov5640ScopePath = Join-Path $RepoRoot 'docs\OV5640_TARGET_SCOPE.md'
$Ov5640C0AuditPath = Join-Path $RepoRoot `
    'docs\OV5640_C0_REFERENCE_AUDIT.md'
$Ov5640ProductRoot = Join-Path $RepoRoot '59_top_dual_ov5640_hdmi'
$Ov5640ProductReadmePath = Join-Path $Ov5640ProductRoot 'README.md'
$Ov5640BoardEvidencePath = Join-Path $Ov5640ProductRoot `
    'doc\BOARD_EVIDENCE.md'
$PcieBaselineDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\H2B_BASELINE_GATE.md'
$PcieBaselineFingerprintPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\H2B_BASELINE_FINGERPRINT.json'
$PcieProvenanceDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\CI8A_BUILD_PROVENANCE.md'
$PcieProvenanceHelperPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\build_provenance.ps1'
$PcieSourceListPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\pds_sources.f'
$PcieSimCheckPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_sim.ps1'
$PcieS2aDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2A_BEHAVIOR_SMOKE.md'
$PcieLinkSimCheckPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_link_sim.ps1'
$PciePostSynSimCheckPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_post_syn_sim.ps1'
$PciePostSynDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2D_POST_SYN_SMOKE.md'
$PciePostPnrFuncSimCheckPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_post_pnr_func_sim.ps1'
$PciePostPnrFuncDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2E_POST_PNR_FUNC_SMOKE.md'
$PciePostPnrTimingSimCheckPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_post_pnr_timing_sim.ps1'
$PciePostPnrTimingDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2F_POST_PNR_TIMING_SMOKE.md'
$PciePostPnrTimingDiagnosticCheckPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_post_pnr_timing_diagnostic.ps1'
$PciePostPnrTimingDiagnosticDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2F_NEGATIVE_TIMING_DIAGNOSTIC.md'
$PcieS2bDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2B_REAL_LINK.md'
$PcieS2cBar1GatePath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\check_s2c_bar1.ps1'
$PcieS2cBar1RegenPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\scripts\regenerate_bar1_staging.ps1'
$SimArchiveGatePath = Join-Path $RepoRoot `
    'scripts\check_sim_archives.ps1'
$ApprovedBoard = '紫光盘古100Pro'
$ApprovedFpgaPart = 'PG2L100H-6IFBG484'
$ApprovedPdsFamily = 'Logos2'
$ApprovedPdsDevice = 'PG2L100H'
$ApprovedPdsPackage = 'FBG484'
$ApprovedPdsSpeedgrade = '-6'
$Ddr3RegeneratePath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\scripts\regenerate_ip.ps1'
$Ddr3RegenerationDocPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\doc\M2_IP_REGENERATION.md'
$Ddr3M2B1AuditPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\doc\M2B1_PARAMETER_AND_DIFF_AUDIT.md'
$Ddr3M2B2BuildPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\scripts\build_staging_compile.tcl'
$Ddr3M2B2RunPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\scripts\run_staging_compile.ps1'
$Ddr3M2B2CheckPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\scripts\check_staging_compile.ps1'
$Ddr3M2B2DocPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\doc\M2B2_STAGING_COMPILE.md'
$Ddr3D3aStagingCheckPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\scripts\check_d3a_staging_contract.ps1'
$Ddr3D3aStagingReviewPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\doc\D3A_PG2L50H_STAGING_REVIEW.md'
$OvM3AuditPath = Join-Path $RepoRoot `
    '41_ov7725_hdmi\doc\M3A_IP_MIGRATION_AUDIT.md'
$OvM3CanonicalIpHashes = [ordered]@{
    '41_ov7725_hdmi\prj\ipcore\ddr3_ip\ddr3_ip.idf' = `
        '4C103420EDF48C5E361A8B7CA132E00EFA268E71B7ABE2BA3826B46A8712E3A1'
    '41_ov7725_hdmi\prj\ipcore\pll_clk\pll_clk.idf' = `
        'B93FDCB80209C0DA3F0BE9BA08E8D1D9E90D37002473C3BA98E5B3C0AB6EF2A1'
    '41_ov7725_hdmi\prj\ipcore\rd_fifo\rd_fifo.idf' = `
        '734DAE3B41599127C648E7012C8E7F5D50945A324981AB52ADBD61195BFB049A'
    '41_ov7725_hdmi\prj\ipcore\wr_fifo\wr_fifo.idf' = `
        'C1C55F4D5C578172B7BA8FBF057163D7E980C9B59C67D99252404A9BDF8E6F70'
}

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
        BoardEvidence = 'doc/BOARD_EVIDENCE.md'
        BoardKeywords = @('OV7725', 'HDMI')
        ReadmePatterns = @{
            Clock = '(?i)cam_pclk|pixel_clk|\u65f6\u949f'
            Interface = '(?i)HDMI|TMDS|DDR3|RGB565'
            Build = 'scripts/(?:build|run)\.ps1|scripts/(?:build|run)\.tcl'
            IpSource = '(?i)IP|IDF|ipcore'
            Blocker = '\u963b\u65ad|\u5c1a\u672a|\u4e0d\u4e00\u81f4|\u5f85\u5ba1\u6838'
        }
    },
    [pscustomobject]@{
        Name = 'DDR3 bring-up'
        Root = 'ddr3_test/ddr3_test'
        Top = 'test_ddr'
        Readme = 'README.md'
        BoardEvidence = 'doc/BOARD_EVIDENCE.md'
        BoardKeywords = @('DDR3', 'test_ddr')
        ReadmePatterns = @{
            Clock = '(?i)free_clk|ui_clk|clk|\u65f6\u949f'
            Interface = '(?i)DDR3|AXI|axi|DQS|DQ'
            Build = 'scripts/(?:build|run)\.ps1|scripts/(?:build|run)\.tcl|[-/]Action\s+build'
            IpSource = '(?i)IP|IDF|ip_core'
            Blocker = '\u963b\u65ad|\u5c1a\u672a|\u4e0d\u4e00\u81f4|\u5f85\u5ba1\u6838'
        }
    },
    [pscustomobject]@{
        Name = 'PCIe DMA'
        Root = 'pcie_dma_test_100h'
        Top = 'pcie_dma_test'
        Readme = 'README.md'
        BoardEvidence = 'doc/PCIE_BOARD_EVIDENCE.md'
        BoardKeywords = @('PCIe', 'H2-A')
        ReadmePatterns = @{
            Clock = '(?i)ref_clk|pclk|clock|\u65f6\u949f'
            Interface = '(?i)PCIe|lane|DMA|UART'
            Build = 'scripts/(?:build|run)\.ps1|scripts/(?:build|run)\.tcl|[-/]Action\s+build'
            IpSource = '(?i)IP|IDF|ipcore'
            Blocker = '\u963b\u65ad|\u5c1a\u672a|\u4e0d\u4e00\u81f4|\u5f85\u5ba1\u6838'
        }
    }
)

Write-Host "INFO: checking repository root $RepoRoot"
Require-File -Path (Join-Path $RepoRoot 'README.md') -Description 'root guide' | Out-Null
Require-File -Path (Join-Path $RepoRoot 'TODO.md') -Description 'root TODO' | Out-Null
Require-File -Path (Join-Path $RepoRoot 'VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md') `
    -Description 'Verilog/SystemVerilog commenting standard' | Out-Null
$GithubWorkflowExists = Require-File -Path $GithubWorkflowPath `
    -Description 'GitHub PR static gate workflow'
$GithubGateDocExists = Require-File -Path $GithubGateDocPath `
    -Description 'GitHub PR static gate guide'
if ($GithubWorkflowExists) {
    $GithubWorkflowText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $GithubWorkflowPath
    foreach ($Required in ([ordered]@{
            'GitHub workflow name' = '(?m)^name:\s*Repository gates\s*$'
            'GitHub pull-request trigger' = '(?m)^\s{2}pull_request:\s*$'
            'GitHub main push trigger' = '(?ms)^\s{2}push:\s*.*?^\s{6}- main\s*$'
            'GitHub manual trigger' = '(?m)^\s{2}workflow_dispatch:\s*$'
            'GitHub read-only permission' = '(?ms)^permissions:\s*.*?^\s{2}contents:\s*read\s*$'
            'GitHub Windows runner' = '(?m)^\s{4}runs-on:\s*windows-latest\s*$'
            'GitHub pwsh shell' = '(?m)^\s{8}shell:\s*pwsh\s*$'
            'GitHub checkout commit pin' = [regex]::Escape(
                "actions/checkout@$GithubCheckoutSha")
            'GitHub full-history checkout' = '(?m)^\s{10}fetch-depth:\s*0\s*$'
            'GitHub credential persistence disabled' =
                '(?m)^\s{10}persist-credentials:\s*false\s*$'
            'GitHub root gate entry' = 'check_repo_consistency\.ps1'
        }).GetEnumerator()) {
        Require-Pattern -Text $GithubWorkflowText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
    if ($GithubWorkflowText -match '(?m)^\s*pull_request_target\s*:') {
        Add-Failure 'GitHub workflow must not use pull_request_target'
    }
    if ($GithubWorkflowText -match '\$\{\{\s*secrets\.') {
        Add-Failure 'GitHub static gate must not read repository secrets'
    }
}
if ($GithubGateDocExists) {
    $GithubGateDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $GithubGateDocPath
    foreach ($Required in ([ordered]@{
            'GitHub gate workflow link' = 'repository-gates\.yml'
            'GitHub gate check name' = 'Static repository gates'
            'GitHub gate no-license boundary' = '不读取 GitHub secrets.*不配置或打印 PDS/Questa 许可证'
            'GitHub gate no-dynamic-claim boundary' = '不表示三个活动项目已经完成实现或四级仿真'
        }).GetEnumerator()) {
        Require-Pattern -Text $GithubGateDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$GitAttributesExists = Require-File -Path $GitAttributesPath `
    -Description 'Git attributes'
if ($GitAttributesExists) {
    $GitAttributesText = Get-Content -Raw -Encoding UTF8 -LiteralPath $GitAttributesPath
    Require-Pattern -Text $GitAttributesText -Pattern '(?m)^\*\.log\s+-diff\s*$' `
        -Description 'historical log no-text-diff rule' | Out-Null
}
$Ov5640ScopeExists = Require-File -Path $Ov5640ScopePath `
    -Description 'OV5640 target scope'
if ($Ov5640ScopeExists) {
    $Ov5640ScopeText = Get-Content -Raw -Encoding UTF8 -LiteralPath $Ov5640ScopePath
    foreach ($Required in ([ordered]@{
            'OV5640 product target' = 'OV5640'
            'OV7725 legacy boundary' = 'OV7725.*(?:legacy|\u5386\u53f2)'
            'approved FPGA target' = 'PG2L100H-6IFBG484'
            'reference import boundary' = '59_top_dual_ov5640_hdmi'
            'Questa validation requirement' = 'Questa.*2021\.1'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ov5640ScopeText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$Ov5640C0AuditExists = Require-File -Path $Ov5640C0AuditPath `
    -Description 'OV5640 C0 reference audit'
if ($Ov5640C0AuditExists) {
    $Ov5640C0AuditText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ov5640C0AuditPath
    foreach ($Required in ([ordered]@{
            'C0 reference commit' = '485f3bba71e4b57fb8bb49cec30e9d331b952be3'
            'C0 complete status' = 'Status: C0 complete; C1 blocked'
            'C0 approved FPGA' = 'PG2L100H-6IFBG484'
            'C0 future project' = '59_top_dual_ov5640_hdmi'
            'C0 old device exclusion' = 'PG2L50H'
            'C0 BAR conflict' = 'BAR1_Enable=false'
            'C0 commenting standard' = 'VSCS'
            'C0 no-import boundary' = 'Import: none'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ov5640C0AuditText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}

$Ov5640ProductReadmeExists = Require-File -Path $Ov5640ProductReadmePath `
    -Description 'dual OV5640 product README'
$Ov5640BoardEvidenceExists = Require-File -Path $Ov5640BoardEvidencePath `
    -Description 'dual OV5640 board evidence checklist'

if ($Ov5640ProductReadmeExists) {
    $Ov5640ProductReadmeText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ov5640ProductReadmePath
    foreach ($Required in ([ordered]@{
            'dual OV5640 product identity' = 'OV5640'
            'dual OV5640 approved board' = [regex]::Escape($ApprovedBoard)
            'dual OV5640 approved FPGA' = [regex]::Escape($ApprovedFpgaPart)
            'dual OV5640 target top' = 'top_dual_ov5640_hdmi'
            'dual OV5640 PDS version' = '2022\.2-SP6\.4'
            'dual OV5640 Questa version' = 'Questa.*2021\.1'
            'dual OV5640 board evidence link' = 'doc/BOARD_EVIDENCE\.md'
            'dual OV5640 commenting standard link' = 'VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD\.md'
            'dual OV5640 no-build boundary' = 'scripts/build\.tcl.*run\.ps1.*check_build\.ps1'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ov5640ProductReadmeText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}

if ($Ov5640BoardEvidenceExists) {
    $Ov5640BoardEvidenceText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ov5640BoardEvidencePath
    foreach ($Required in ([ordered]@{
            'dual OV5640 current-facts section' = '(?m)^##\s+\u5f53\u524d\u5de5\u7a0b\u4e8b\u5b9e\s*$'
            'dual OV5640 required-materials section' = '(?m)^##\s+\u5fc5\u987b\u63d0\u4f9b\u7684\u8d44\u6599\s*$'
            'dual OV5640 closure section' = '(?m)^##\s+\u5173\u95ed\u6761\u4ef6\s*$'
            'dual OV5640 approved board evidence' = [regex]::Escape($ApprovedBoard)
            'dual OV5640 approved FPGA evidence' = [regex]::Escape($ApprovedFpgaPart)
            'dual OV5640 reference commit' = '485f3bba71e4b57fb8bb49cec30e9d331b952be3'
            'dual OV5640 C1 blocker' = 'C1/H3'
            'dual OV5640 VSCS boundary' = 'VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD\.md'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ov5640BoardEvidenceText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
    foreach ($Keyword in @('OV5640', 'MCLK', 'RESET', 'PWDN', 'DVP', 'DDR3', 'HDMI', 'PG2L100H')) {
        Require-Pattern -Text $Ov5640BoardEvidenceText `
            -Pattern ([regex]::Escape($Keyword)) `
            -Description "dual OV5640 board evidence keyword '$Keyword'" | Out-Null
    }
}

if (Test-Path -LiteralPath $Ov5640ProductRoot -PathType Container) {
    $AllowedOv5640C1Files = @(
        $Ov5640ProductReadmePath,
        $Ov5640BoardEvidencePath
    )
    $UnexpectedOv5640C1Files = @(Get-ChildItem -LiteralPath $Ov5640ProductRoot `
            -Recurse -File | Where-Object {
                $_.FullName -notin $AllowedOv5640C1Files
            })
    foreach ($UnexpectedFile in $UnexpectedOv5640C1Files) {
        Add-Failure "Dual OV5640 C1-A contains unreviewed design file: $($UnexpectedFile.FullName)"
    }

    foreach ($ForbiddenEntry in @(
            'scripts\build.tcl',
            'scripts\run.ps1',
            'scripts\check_build.ps1',
            'sim\questa'
        )) {
        $ForbiddenPath = Join-Path $Ov5640ProductRoot $ForbiddenEntry
        if (Test-Path -LiteralPath $ForbiddenPath) {
            Add-Failure "Dual OV5640 C1-A contains premature entry: $ForbiddenPath"
        }
    }
    Write-Host 'INFO: dual OV5640 C1-A product boundary checked'
}

$PdsTclInventoryDocExists = Require-File -Path $PdsTclInventoryDocPath `
    -Description 'PDS Tcl entrypoint inventory guide'
$PdsTclInventoryExists = Require-File -Path $PdsTclInventoryPath `
    -Description 'PDS Tcl entrypoint machine inventory'
$PdsTclGateExists = Require-File -Path $PdsTclGatePath `
    -Description 'PDS Tcl entrypoint gate'
if ($PdsTclInventoryDocExists) {
    $PdsTclInventoryDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PdsTclInventoryDocPath
    foreach ($Required in ([ordered]@{
            'CI-7 canonical project build role' = 'canonical_project_build'
            'CI-7 migration-blocked build role' = 'migration_blocked_project_build'
            'CI-7 historical GUI role' = 'historical_gui'
            'CI-7 vendor internal role' = 'vendor_generated_internal'
            'CI-7 machine inventory link' = 'PDS_TCL_ENTRYPOINT_INVENTORY\.json'
        }).GetEnumerator()) {
        Require-Pattern -Text $PdsTclInventoryDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($PdsTclInventoryExists -and $PdsTclGateExists) {
    try {
        & $PdsTclGatePath -RepoRoot $RepoRoot -InventoryPath $PdsTclInventoryPath
        if ($LASTEXITCODE -ne 0) {
            Add-Failure 'PDS Tcl entrypoint inventory gate failed'
        }
    } catch {
        Add-Failure ("PDS Tcl entrypoint inventory gate failed: {0}" -f `
                $_.Exception.Message)
    }
}

$SensitiveDiffGateExists = Require-File -Path $SensitiveDiffGatePath `
    -Description 'license sensitive diff gate'
$SensitiveDiffGateDocExists = Require-File -Path $SensitiveDiffGateDocPath `
    -Description 'license sensitive diff gate guide'
if ($SensitiveDiffGateDocExists) {
    $SensitiveDiffGateDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $SensitiveDiffGateDocPath
    foreach ($Required in ([ordered]@{
            'sensitive diff gate command' = 'check_sensitive_diff\.ps1'
            'sensitive diff gate base ref' = 'BaseRef'
            'sensitive diff gate history boundary' = '\u5386\u53f2'
            'sensitive diff gate placeholder rule' = '<license-source>'
        }).GetEnumerator()) {
        Require-Pattern -Text $SensitiveDiffGateDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($SensitiveDiffGateExists) {
    try {
        & $SensitiveDiffGatePath -RepoRoot $RepoRoot -SelfTest
        if ($LASTEXITCODE -ne 0) {
            Add-Failure 'License sensitive diff gate self-test failed'
        }
        & $SensitiveDiffGatePath -RepoRoot $RepoRoot -FullTree
        if ($LASTEXITCODE -ne 0) {
            Add-Failure 'License sensitive full-tree gate failed'
        }
        & $SensitiveDiffGatePath -RepoRoot $RepoRoot `
            -BaseRef $SensitiveDiffBaseRef
        if ($LASTEXITCODE -ne 0) {
            Add-Failure 'License sensitive diff gate failed'
        }
    } catch {
        Add-Failure ("License sensitive diff gate failed: {0}" -f `
                $_.Exception.Message)
    }
}

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

$SimArchiveGateExists = Require-File -Path $SimArchiveGatePath `
    -Description 'three-project simulation archive gate'
if ($SimArchiveGateExists) {
    try {
        & $SimArchiveGatePath -RepoRoot $RepoRoot
        if ($LASTEXITCODE -ne 0) {
            Add-Failure 'Three-project simulation archive gate failed'
        }
    } catch {
        Add-Failure ("Three-project simulation archive gate failed: {0}" -f `
                $_.Exception.Message)
    }
}

$PcieS2cBar1GateExists = Require-File -Path $PcieS2cBar1GatePath `
    -Description 'PCIe S2-C BAR1 regeneration gate'
if ($PcieS2cBar1GateExists) {
    try {
        Push-Location (Join-Path $RepoRoot 'pcie_dma_test_100h')
        & $PcieS2cBar1GatePath
        if ($LASTEXITCODE -ne 0) {
            Add-Failure 'PCIe S2-C BAR1 regeneration gate failed'
        }
    } catch {
        Add-Failure ("PCIe S2-C BAR1 regeneration gate failed: {0}" -f $_.Exception.Message)
    } finally {
        Pop-Location
    }
}
$PcieS2cBar1RegenExists = Require-File -Path $PcieS2cBar1RegenPath `
    -Description 'PCIe S2-C BAR1 staging regeneration entry'
if ($PcieS2cBar1RegenExists) {
    $PcieS2cBar1RegenText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieS2cBar1RegenPath
    foreach ($Required in @(
            'ip_generate\.exe',
            'build\\ipgen\\pcie_bar1',
            '-family Logos2',
            '-device PG2L50H',
            '-pack FBG484',
            '-speed -6',
            '(?i)canonical generated IP is untouched',
            'dry run only')) {
        Require-Pattern -Text $PcieS2cBar1RegenText -Pattern $Required `
            -Description "BAR1 staging regeneration contract '$Required'" | Out-Null
    }
}

$Ddr3RegenerateExists = Require-File -Path $Ddr3RegeneratePath `
    -Description 'DDR3 PG2L50H staging regeneration entry'
$Ddr3RegenerationDocExists = Require-File -Path $Ddr3RegenerationDocPath `
    -Description 'DDR3 M2 IP regeneration audit'
$Ddr3M2B1AuditExists = Require-File -Path $Ddr3M2B1AuditPath `
    -Description 'DDR3 M2-B1 parameter and diff audit'
$Ddr3M2B2BuildExists = Require-File -Path $Ddr3M2B2BuildPath `
    -Description 'DDR3 M2-B2 staging compile Tcl'
$Ddr3M2B2RunExists = Require-File -Path $Ddr3M2B2RunPath `
    -Description 'DDR3 M2-B2 staging compile runner'
$Ddr3M2B2CheckExists = Require-File -Path $Ddr3M2B2CheckPath `
    -Description 'DDR3 M2-B2 staging compile gate'
$Ddr3M2B2DocExists = Require-File -Path $Ddr3M2B2DocPath `
    -Description 'DDR3 M2-B2 staging compile contract'
if ($Ddr3RegenerateExists) {
    $Ddr3RegenerateText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3RegeneratePath
    foreach ($Required in ([ordered]@{
            'PDS IP generator invocation' = 'ip_generate\.exe'
            'approved DDR3 device override' = '-device\s+PG2L50H'
            'approved DDR3 package override' = '-pack\s+FBG484'
            'approved DDR3 speed override' = '-speed\s+-6'
            'staging under build directory' = "'build'"
            'validated PG2L50H seed' = 'ip_backup\\20250108100125\\ddr3'
            'case-sensitive IDF parameter comparison' = 'Sort-Object\s+-CaseSensitive'
            'order-independent IDF parameter diff' = 'Compare-Object'
            'canonical hash preservation gate' = 'Get-FileHash'
            'DEVICE_100H_EN false gate' = "DEVICE_100H_EN.*false"
            'PG2L50H PPLL synthesis gate' = 'CLKOUT4_SYN_EN'
            'PG2L50H PPLL feedback gate' = 'INTERNAL_FB'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3RegenerateText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($Ddr3RegenerationDocExists) {
    $Ddr3RegenerationDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3RegenerationDocPath
    foreach ($Required in ([ordered]@{
            'M2 staging legacy FPGA part' = 'PG2L50H-6IFBG484'
            'M2 canonical promotion conditions' = '(?m)^##\s+\u5347\u683c\u6761\u4ef6\s*\r?$'
            'M2 rollback conditions' = '(?m)^##\s+\u56de\u9000\u6761\u4ef6\s*\r?$'
            'M2 wrapper clock drift' = 'ref_clk_p/ref_clk_n'
            'M2 derived device parameter gate' = 'DEVICE_100H_EN=false'
            'M2-B1 audit link' = 'M2B1_PARAMETER_AND_DIFF_AUDIT\.md'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3RegenerationDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($Ddr3M2B1AuditExists) {
    $Ddr3M2B1AuditText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3M2B1AuditPath
    foreach ($Required in ([ordered]@{
            'M2-B1 hidden parameter conclusion' = '\u9690\u85cf\u5668\u4ef6\u6d3e\u751f\u53c2\u6570'
            'M2-B1 PG2L50H false value' = 'PG2L50H.*false'
            'M2-B1 PPLL branch evidence' = 'CLKOUT4_SYN_EN.*TRUE'
            'M2-B1 added port count' = '21\s*\u4e2a\u589e\u52a0\u5230\s*26\s*\u4e2a'
            'M2-B1 pin diff count' = '28\s*\u9879\u5dee\u5f02'
            'M2-B1 canonical promotion boundary' = '(?m)^##\s+\u5347\u683c\u8fb9\u754c\s*\r?$'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3M2B1AuditText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}

# M3-A is now a frozen-legacy gate. Protect the four active IDFs from drift;
# OV7725 will not be promoted to PG2L50H, and dual OV5640 uses a new project.
$OvM3AuditExists = Require-File -Path $OvM3AuditPath `
    -Description 'OV7725 M3-A four-IP migration audit'
if ($OvM3AuditExists) {
    $OvM3AuditText = Get-Content -Raw -Encoding UTF8 -LiteralPath $OvM3AuditPath
    foreach ($Required in ([ordered]@{
            'M3-A legacy FPGA part' = 'PG2L50H-6IFBG484'
            'M3-A old-IP path rejection' = 'IPCompiler 0037'
            'M3-A version mismatch rejection' = 'IPCompiler 0057'
            'M3-A DDR3 version gap' = '1\.12.*1\.10'
            'M3-A PLL version gap' = '1\.3.*1\.5'
            'M3-A FIFO version gap' = '1\.8.*1\.10'
            'M3-A GUI new-instance rule' = 'SP6\.4 IP Compiler GUI'
            'M3-A staging-only output' = 'build/ipgen/pg2l50h'
            'M3-A canonical promotion block' = '\u7981\u6b62 canonical \u5347\u683c'
            'M3-A DDR3 derived parameter' = 'DEVICE_100H_EN=false'
            'M3-A PLL derived parameter' = 'DEVICE_PG2L50H=true'
            'M3-A FIFO PG2L50H resource limits' = '85 \u4e2a DRM36K/170 \u4e2a DRM18K'
            'M3-A RCF object-hit review' = 'RCF.*\u5bf9\u8c61.*\u547d\u4e2d'
        }).GetEnumerator()) {
        Require-Pattern -Text $OvM3AuditText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}

foreach ($Entry in $OvM3CanonicalIpHashes.GetEnumerator()) {
    $IdfPath = Join-Path $RepoRoot $Entry.Key
    if (Require-File -Path $IdfPath -Description "OV7725 canonical IP $($Entry.Key)") {
        $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $IdfPath).Hash
        if ($ActualHash -ne $Entry.Value) {
            Add-Failure "OV7725 frozen legacy IP changed: $($Entry.Key)"
        } else {
            Write-Host "INFO: OV7725 canonical IP hash preserved: $($Entry.Key)"
        }
    }
}

$RootReadmePath = Join-Path $RepoRoot 'README.md'
$TodoPath = Join-Path $RepoRoot 'TODO.md'
$MatrixExists = Require-File -Path $MatrixPath -Description 'simulation readiness matrix'
if ($MatrixExists) {
    $MatrixText = Get-Content -Raw -Encoding UTF8 -LiteralPath $MatrixPath
    Require-Pattern -Text $MatrixText -Pattern 'OV7725 legacy' `
        -Description 'simulation matrix OV7725 legacy boundary' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'OV5640' `
        -Description 'simulation matrix OV5640 target coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'DDR3' `
        -Description 'simulation matrix DDR3 coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'PCIe DMA' `
        -Description 'simulation matrix PCIe coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S1 DDR3' `
        -Description 'simulation matrix S1 DDR3 queue' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S2 PCIe' `
        -Description 'simulation matrix S2 PCIe queue' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S3.*OV5640' `
        -Description 'simulation matrix S3 dual OV5640 queue' | Out-Null
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
    Require-Pattern -Text $TodoText -Pattern ([regex]::Escape($ApprovedBoard)) `
        -Description 'approved shared board in TODO' | Out-Null
    Require-Pattern -Text $TodoText -Pattern ([regex]::Escape($ApprovedFpgaPart)) `
        -Description 'approved FPGA part in TODO' | Out-Null
    Require-Pattern -Text $TodoText `
        -Pattern 'DDR3.{1,12}PCIe.{1,24}OV5640' `
        -Description 'TODO dual OV5640 active-project boundary' | Out-Null
    Require-Pattern -Text $TodoText `
        -Pattern '59_top_dual_ov5640_hdmi/.*doc/BOARD_EVIDENCE\.md' `
        -Description 'TODO dual OV5640 board-evidence task' | Out-Null

    $ActiveOv7725Tasks = @($TodoText -split "`r?`n" | Where-Object {
            $_ -match '^\s*-\s*\[\s\]\s+.*OV7725'
        })
    if ($ActiveOv7725Tasks.Count -gt 0) {
        Add-Failure "TODO contains active OV7725 tasks: $($ActiveOv7725Tasks -join ' | ')"
    } else {
        Write-Host 'INFO: TODO contains no active OV7725 tasks'
    }
}

$IgnoreText = Get-Content -Raw -LiteralPath (Join-Path $RepoRoot '.gitignore')
Require-Pattern -Text $IgnoreText -Pattern '(?m)^build/\r?$' `
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
    $BoardEvidencePath = Join-Path $ProjectRoot ($Project.BoardEvidence -replace '/', '\')

    $ReadmeExists = Require-File -Path $ReadmePath -Description "$($Project.Name) README"
    $BuildExists = Require-File -Path $BuildPath -Description "$($Project.Name) build.tcl"
    $RunExists = Require-File -Path $RunPath -Description "$($Project.Name) run.ps1"
    $GateExists = Require-File -Path $GatePath -Description "$($Project.Name) check_build.ps1"
    $BoardEvidenceExists = Require-File -Path $BoardEvidencePath -Description "$($Project.Name) board evidence checklist"

    if ($ReadmeExists) {
        $ReadmeText = Get-Content -Raw -Encoding UTF8 -LiteralPath $ReadmePath
        $TopPattern = [regex]::Escape($Project.Top)
        Require-Pattern -Text $ReadmeText -Pattern '2022\.2-SP6\.4' `
            -Description "$($Project.Name) PDS version in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $TopPattern `
            -Description "$($Project.Name) top module in README" | Out-Null
        Require-Pattern -Text $ReadmeText `
            -Pattern '(?i)ModelSim|Questa(?:Sim| Sim-64)|USIM|VSIM' `
            -Description "$($Project.Name) simulation status in README" | Out-Null
        $EvidenceLinkPattern = [regex]::Escape(($Project.BoardEvidence -replace '\\', '/'))
        Require-Pattern -Text $ReadmeText -Pattern $EvidenceLinkPattern `
            -Description "$($Project.Name) board evidence link in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $Project.ReadmePatterns.Clock `
            -Description "$($Project.Name) clock summary in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $Project.ReadmePatterns.Interface `
            -Description "$($Project.Name) interface summary in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $Project.ReadmePatterns.Build `
            -Description "$($Project.Name) build command in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $Project.ReadmePatterns.IpSource `
            -Description "$($Project.Name) IP/source summary in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern $Project.ReadmePatterns.Blocker `
            -Description "$($Project.Name) known-blocker summary in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern ([regex]::Escape($ApprovedFpgaPart)) `
            -Description "$($Project.Name) approved FPGA part in README" | Out-Null
        Require-Pattern -Text $ReadmeText -Pattern ([regex]::Escape($ApprovedPdsDevice)) `
            -Description "$($Project.Name) approved PDS device in README" | Out-Null
    }

    if ($BoardEvidenceExists) {
        $BoardEvidenceText = Get-Content -Raw -Encoding UTF8 -LiteralPath $BoardEvidencePath
        Require-Pattern -Text $BoardEvidenceText -Pattern '(?m)^##\s+(?:\d+\.\s*)?\u5f53\u524d\u5de5\u7a0b\u4e8b\u5b9e\s*$' `
            -Description "$($Project.Name) board evidence current-facts section" | Out-Null
        Require-Pattern -Text $BoardEvidenceText -Pattern '(?m)^##\s+(?:\d+\.\s*)?\u5fc5\u987b\u63d0\u4f9b\u7684\u8d44\u6599\s*$' `
            -Description "$($Project.Name) board evidence required-materials section" | Out-Null
        Require-Pattern -Text $BoardEvidenceText -Pattern '(?m)^##\s+(?:\d+\.\s*)?\u5173\u95ed\u6761\u4ef6\s*$' `
            -Description "$($Project.Name) board evidence closure section" | Out-Null
        foreach ($Keyword in $Project.BoardKeywords) {
            Require-Pattern -Text $BoardEvidenceText -Pattern ([regex]::Escape($Keyword)) `
                -Description "$($Project.Name) board evidence keyword '$Keyword'" | Out-Null
        }
        Require-Pattern -Text $BoardEvidenceText -Pattern ([regex]::Escape($ApprovedBoard)) `
            -Description "$($Project.Name) approved shared board in evidence" | Out-Null
        Require-Pattern -Text $BoardEvidenceText -Pattern ([regex]::Escape($ApprovedFpgaPart)) `
            -Description "$($Project.Name) approved FPGA part in evidence" | Out-Null
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
        Require-Pattern -Text $RunText -Pattern '\^E:' `
            -Description "$($Project.Name) PDS error-log check" | Out-Null
        Require-Pattern -Text $RunText -Pattern '(?i)stage|RunTo' `
            -Description "$($Project.Name) stage completion handling" | Out-Null
    }

    if ($GateExists) {
        $GateText = Get-Content -Raw -Encoding UTF8 -LiteralPath $GatePath
        Require-Pattern -Text $GateText -Pattern 'AllowKnownBaselineIssues' `
            -Description "$($Project.Name) explicit baseline switch" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)Test-Path|Assert-NonEmptyFile' `
            -Description "$($Project.Name) artifact existence check" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)Timing|WNS|TNS|Constraints Met' `
            -Description "$($Project.Name) timing gate" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)Assert-NonEmptyFile|Test-Path' `
            -Description "$($Project.Name) non-empty artifact gate" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)RequiredLogPatterns|StageOrder|BuildLog|RunTo' `
            -Description "$($Project.Name) stage or final-build gate" | Out-Null
        Require-Pattern -Text $GateText -Pattern '(?i)throw' `
            -Description "$($Project.Name) strict failure behavior" | Out-Null
    }
}

# Parse the active PCIe IP structurally. During the PG2L100H recovery batch a
# PG2L50H IDF is an explicitly documented blocker, not an approved match.
$PcieIdfPath = Join-Path $RepoRoot 'pcie_dma_test_100h\ipcore\pcie_test\pcie_test.idf'
if (Require-File -Path $PcieIdfPath -Description 'active PCIe IP definition') {
    try {
        [xml]$PcieIdfXml = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieIdfPath
        $PcieIdfDevice = [string]$PcieIdfXml.ip_inst.header.device
        if ($PcieIdfDevice -ne $ApprovedPdsDevice) {
            if ($PcieIdfDevice -eq 'PG2L50H') {
                Write-Host "WARN: PCIe IP remains PG2L50H during PG2L100H recovery; migration is blocked"
            } else {
                Add-Failure "PCIe IP targets '$PcieIdfDevice'; approved device is '$ApprovedPdsDevice'"
            }
        } else {
            Write-Host "INFO: PCIe IP matches approved device $ApprovedPdsDevice"
        }
    } catch {
        Add-Failure "PCIe IP definition is not valid XML: $PcieIdfPath"
    }
}

$PcieBaselineDocExists = Require-File `
    -Path $PcieBaselineDocPath `
    -Description 'PCIe H2-B0 baseline gate guide'
$PcieBaselineFingerprintExists = Require-File `
    -Path $PcieBaselineFingerprintPath `
    -Description 'PCIe H2-B0 machine fingerprint'
if ($PcieBaselineDocExists) {
    $PcieBaselineDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PcieBaselineDocPath
    foreach ($Required in ([ordered]@{
            'PCIe H2-B0 unique signature contract' = '16\s*\u4e2a\u552f\u4e00\u7b7e\u540d'
            'PCIe H2-B0 raw occurrence contract' = '42\s*\u6761\u539f\u59cb\u8bb0\u5f55'
            'PCIe H2-B1 external boundary' = 'H2-B1'
            'PCIe CI-8 provenance boundary' = 'CI-8'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieBaselineDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($PcieBaselineFingerprintExists) {
    try {
        $PcieBaselineFingerprint = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $PcieBaselineFingerprintPath | ConvertFrom-Json
        if ($PcieBaselineFingerprint.schema_version -ne 1) {
            Add-Failure 'PCIe H2-B0 fingerprint schema is not 1'
        }
        $PcieSignatures = @($PcieBaselineFingerprint.signatures)
        $PcieDuplicateSignatures = @($PcieSignatures |
                Group-Object -Property signature | Where-Object Count -gt 1)
        if ($PcieDuplicateSignatures.Count -gt 0) {
            Add-Failure 'PCIe H2-B0 fingerprint contains duplicate signatures'
        }
        $PcieRawOccurrences = ($PcieSignatures.occurrences |
                Measure-Object -Sum).Sum
        if ($PcieSignatures.Count -ne 16 -or $PcieRawOccurrences -ne 42 -or
            $PcieBaselineFingerprint.expected_unique_signatures -ne 16 -or
            $PcieBaselineFingerprint.expected_raw_occurrences -ne 42) {
            Add-Failure 'PCIe H2-B0 fingerprint must contain 16 signatures and 42 occurrences'
        }
        # H2-B0 is a frozen PG2L50H migration fingerprint. It remains
        # auditable, but is not the current PG2L100H acceptance target.
        foreach ($Field in ([ordered]@{
                family = $ApprovedPdsFamily
                device = 'PG2L50H'
                package = $ApprovedPdsPackage
                speedgrade = $ApprovedPdsSpeedgrade
            }).GetEnumerator()) {
            $ActualValue = [string]$PcieBaselineFingerprint.approved_target.($Field.Key)
            if ($ActualValue -ne $Field.Value) {
                Add-Failure "PCIe H2-B0 fingerprint $($Field.Key) is '$ActualValue'; expected '$($Field.Value)'"
            }
        }
    } catch {
        Add-Failure "PCIe H2-B0 fingerprint is not valid JSON: $PcieBaselineFingerprintPath"
    }
}

$PcieGatePath = Join-Path $RepoRoot 'pcie_dma_test_100h\scripts\check_build.ps1'
if (Test-Path -LiteralPath $PcieGatePath -PathType Leaf) {
    $PcieGateText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieGatePath
    foreach ($Required in ([ordered]@{
            'PCIe H2-B0 fingerprint input' = 'BaselineFingerprintPath'
            'PCIe H2-B0 signature parser' = 'Get-BaselineIssueSignatureCounts'
            'PCIe H2-B0 drift hard failure' = 'baseline fingerprint changed'
            'PCIe metadata unconditional failure' = 'PCIe IP metadata gate failed'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieGateText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PcieProvenanceDocExists = Require-File `
    -Path $PcieProvenanceDocPath `
    -Description 'PCIe CI-8A build provenance contract'
$PcieProvenanceHelperExists = Require-File `
    -Path $PcieProvenanceHelperPath `
    -Description 'PCIe CI-8A provenance helper'
$PcieSourceListExists = Require-File `
    -Path $PcieSourceListPath `
    -Description 'PCIe canonical PDS source list'

if ($PcieProvenanceDocExists) {
    $PcieProvenanceDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PcieProvenanceDocPath
    foreach ($Required in ([ordered]@{
            'PCIe CI-8A 43-input contract' = '43\s*\u9879\s*canonical'
            'PCIe CI-8A nine-artifact contract' = '(?:9|\u4e5d)\s*\u9879\s*\u6700\u7ec8\u8bc1\u636e'
            'PCIe CI-8A functional netlist artifact' = 'pcie_dma_test_func\.v'
            'PCIe CI-8A functional netlist log artifact' = 'pds-post-pnr-func-netlist\.log'
            'PCIe CI-8A partial rejection' = '`partial`'
            'PCIe CI-8A failed rejection' = '`failed`'
            'PCIe CI-8B migration boundary' = 'CI-8B'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieProvenanceDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}

if ($PcieSourceListExists) {
    $PcieSourcePaths = @(Get-Content -LiteralPath $PcieSourceListPath |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') })
    if ($PcieSourcePaths.Count -ne 37) {
        Add-Failure "PCIe canonical PDS source list must contain 37 paths; found $($PcieSourcePaths.Count)"
    }
    $PcieDuplicateSourcePaths = @($PcieSourcePaths |
        Group-Object -CaseSensitive | Where-Object Count -gt 1)
    if ($PcieDuplicateSourcePaths.Count -gt 0) {
        Add-Failure 'PCIe canonical PDS source list contains duplicate paths'
    }
    foreach ($RelativePath in $PcieSourcePaths) {
        if ([IO.Path]::IsPathRooted($RelativePath) -or
            $RelativePath -match '(^|/)\.\.(/|$)') {
            Add-Failure "PCIe canonical PDS source path is not project-relative: $RelativePath"
            continue
        }
        Require-File `
            -Path (Join-Path $RepoRoot "pcie_dma_test_100h\$($RelativePath -replace '/', '\')") `
            -Description "PCIe canonical source $RelativePath" | Out-Null
    }
}

$PcieRunPath = Join-Path $RepoRoot 'pcie_dma_test_100h\scripts\run.ps1'
$PcieBuildPath = Join-Path $RepoRoot 'pcie_dma_test_100h\scripts\build.tcl'
if (Test-Path -LiteralPath $PcieRunPath -PathType Leaf) {
    $PcieRunText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieRunPath
    foreach ($Required in ([ordered]@{
            'PCIe CI-8A run-id environment' = 'PDS_RUN_ID'
            'PCIe CI-8A initial running manifest' = "status = 'running'"
            'PCIe CI-8A failed manifest' = "status = 'failed'"
            'PCIe CI-8A atomic manifest writer' = 'Write-PdsProvenanceManifest'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieRunText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if (Test-Path -LiteralPath $PcieBuildPath -PathType Leaf) {
    $PcieBuildText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieBuildPath
    foreach ($Required in ([ordered]@{
            'PCIe CI-8A source-list consumer' = 'pds_sources\.f'
            'PCIe CI-8A Tcl run marker' = 'PDS_RUN_ID='
            'PCIe CI-8A Tcl completion marker' = 'PDS_RUN_COMPLETE='
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieBuildText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($PcieProvenanceHelperExists) {
    $PcieProvenanceHelperText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PcieProvenanceHelperPath
    foreach ($Required in ([ordered]@{
            'PCIe CI-8A canonical input enumerator' = 'Get-PdsCanonicalInputPaths'
            'PCIe CI-8A artifact enumerator' = 'Get-PdsArtifactPaths'
            'PCIe CI-8A SHA-256 records' = 'Get-FileHash\s+-Algorithm\s+SHA256'
            'PCIe CI-8A atomic replace' = '\[IO\.File\]::Replace'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieProvenanceHelperText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if (Test-Path -LiteralPath $PcieGatePath -PathType Leaf) {
    $PcieGateText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieGatePath
    foreach ($Required in ([ordered]@{
            'PCIe CI-8A manifest input' = 'provenance\\pds-build\.json'
            'PCIe CI-8A record comparison' = 'Assert-PdsFileRecordsMatch'
            'PCIe CI-8A complete run requirement' = "status\s+-cne\s+'complete'"
            'PCIe CI-8A final stage requirement' = "run_to\s+-cne\s+'gen_bit_stream'"
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieGateText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PcieSimCheckExists = Require-File `
    -Path $PcieSimCheckPath `
    -Description 'PCIe S2-A static simulation gate'
if ($PcieSimCheckExists) {
    try {
        & $PcieSimCheckPath
    } catch {
        Add-Failure "PCIe S2-A static simulation gate failed: $($_.Exception.Message)"
    }
}
$PcieLinkSimCheckExists = Require-File `
    -Path $PcieLinkSimCheckPath `
    -Description 'PCIe S2-B static simulation gate'
if ($PcieLinkSimCheckExists) {
    try {
        & $PcieLinkSimCheckPath
    } catch {
        Add-Failure "PCIe S2-B static simulation gate failed: $($_.Exception.Message)"
    }
}
$PciePostSynSimCheckExists = Require-File `
    -Path $PciePostSynSimCheckPath `
    -Description 'PCIe post-synthesis static simulation gate'
if ($PciePostSynSimCheckExists) {
    try {
        & $PciePostSynSimCheckPath
    } catch {
        Add-Failure "PCIe post-synthesis static simulation gate failed: $($_.Exception.Message)"
    }
}
$PciePostPnrFuncSimCheckExists = Require-File `
    -Path $PciePostPnrFuncSimCheckPath `
    -Description 'PCIe post-PNR functional static simulation gate'
if ($PciePostPnrFuncSimCheckExists) {
    try {
        & $PciePostPnrFuncSimCheckPath
    } catch {
        Add-Failure "PCIe post-PNR functional static simulation gate failed: $($_.Exception.Message)"
    }
}
if ($Ddr3M2B2BuildExists -and $Ddr3M2B2RunExists -and
    $Ddr3M2B2CheckExists -and $Ddr3M2B2DocExists) {
    $Ddr3M2B2BuildText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3M2B2BuildPath
    $Ddr3M2B2RunText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3M2B2RunPath
    $Ddr3M2B2DocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3M2B2DocPath

    foreach ($Required in ([ordered]@{
            'M2-B2 PG2L50H target' = '-device\s+PG2L50H'
            'M2-B2 compile-only command' = 'compile\s+-top_module\s+test_ddr'
            'M2-B2 staging IDF' = '\$staging_root/ddr3\.idf'
            'M2-B2 18-source contract' = 'M2B2_SOURCE_COUNT='
            'M2-B2 success marker' = 'M2B2_COMPILE_OK'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3M2B2BuildText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
    foreach ($ForbiddenPattern in @(
            'add_constraint',
            '\bsynthesize\b',
            '\bdev_map\b',
            '(?m)^\s*pnr\b'
        )) {
        if ($Ddr3M2B2BuildText -match $ForbiddenPattern) {
            Add-Failure "M2-B2 compile Tcl contains forbidden pattern: $ForbiddenPattern"
        }
    }
    foreach ($Required in ([ordered]@{
            'M2-B2 fresh regeneration' = 'regenerate_ip\.ps1'
            'M2-B2 canonical hash gate' = 'Get-CanonicalHashes'
            'M2-B2 license redaction' = 'details redacted'
            'M2-B2 dynamic gate' = 'check_staging_compile\.ps1'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3M2B2RunText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
    foreach ($Required in @(
            '1d4b8c264ba940f0bb0e2517b8c36c07',
            '18 \u4e2a staging RTL',
            '0 / 272',
            'canonical',
            'VCCIO.*VREF.*ODT'
        )) {
        Require-Pattern -Text $Ddr3M2B2DocText -Pattern $Required `
            -Description "M2-B2 evidence '$Required'" | Out-Null
    }

    try {
        & $Ddr3M2B2CheckPath -StaticOnly -SelfTest
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "M2-B2 static gate exited with code $LASTEXITCODE"
        }
    } catch {
        Add-Failure "M2-B2 static gate failed: $($_.Exception.Message)"
    }
}
$Ddr3D3aStagingCheckExists = Require-File `
    -Path $Ddr3D3aStagingCheckPath `
    -Description 'DDR3 D3-0-M staging contract gate'
$Ddr3D3aStagingReviewExists = Require-File `
    -Path $Ddr3D3aStagingReviewPath `
    -Description 'DDR3 D3-0-M staging contract review'
if ($Ddr3D3aStagingCheckExists -and $Ddr3D3aStagingReviewExists) {
    $Ddr3D3aStagingCheckText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3D3aStagingCheckPath
    $Ddr3D3aStagingReviewText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3D3aStagingReviewPath

    foreach ($Required in ([ordered]@{
            'D3-0-M five-port delta' = 'ExpectedAddedWrapperPorts'
            'D3-0-M differential input buffer' = 'GTP_INBUFDS'
            'D3-0-M refclk connection comparison' = 'I_ips_ddr_top.*ref_clk'
            'D3-0-M negative self-test' = 'Invoke-NegativeSelfTest'
            'D3-0-M static mode' = 'StaticOnly'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3D3aStagingCheckText `
            -Pattern $Required.Value -Description $Required.Key | Out-Null
    }
    foreach ($Required in @(
            'ref_clk_p/ref_clk_n',
            'GTP_INBUFDS',
            'D3-A.*blocked',
            'PG2L50H-6IFBG484',
            'axi_wready.*axi_wusero_last'
        )) {
        Require-Pattern -Text $Ddr3D3aStagingReviewText `
            -Pattern $Required -Description "D3-0-M evidence '$Required'" |
            Out-Null
    }

    try {
        & $Ddr3D3aStagingCheckPath -StaticOnly -SelfTest
    } catch {
        Add-Failure "D3-0-M static gate failed: $($_.Exception.Message)"
    }
}
$ConstraintExceptionGateExists = Require-File `
    -Path $ConstraintExceptionGatePath `
    -Description 'constraint exception inventory gate'
$ConstraintExceptionInventoryExists = Require-File `
    -Path $ConstraintExceptionInventoryPath `
    -Description 'constraint exception machine inventory'
$ConstraintExceptionInventoryDocExists = Require-File `
    -Path $ConstraintExceptionInventoryDocPath `
    -Description 'constraint exception inventory guide'
if ($ConstraintExceptionGateExists -and
    $ConstraintExceptionInventoryExists -and
    $ConstraintExceptionInventoryDocExists) {
    try {
        & $ConstraintExceptionGatePath -RepoRoot $RepoRoot `
            -InventoryPath $ConstraintExceptionInventoryPath -SelfTest
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "constraint exception gate exited with code $LASTEXITCODE"
        }
    } catch {
        Add-Failure "constraint exception gate failed: $($_.Exception.Message)"
    }

    $ConstraintExceptionDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $ConstraintExceptionInventoryDocPath
    foreach ($Required in ([ordered]@{
            'constraint inventory machine link' =
                'CONSTRAINT_EXCEPTION_INVENTORY\.json'
            'constraint inventory gate link' =
                'check_constraint_exceptions\.ps1'
            'constraint inventory no-waiver boundary' =
                '例外合理或已批准'
            'constraint inventory dual OV5640 boundary' =
                '双 OV5640.*H3 blocked|H3.*双 OV5640'
        }).GetEnumerator()) {
        Require-Pattern -Text $ConstraintExceptionDocText `
            -Pattern $Required.Value -Description $Required.Key | Out-Null
    }
}
$PciePostPnrTimingSimCheckExists = Require-File `
    -Path $PciePostPnrTimingSimCheckPath `
    -Description 'PCIe post-PNR timing static simulation gate'
if ($PciePostPnrTimingSimCheckExists) {
    try {
        & $PciePostPnrTimingSimCheckPath
    } catch {
        Add-Failure "PCIe post-PNR timing static simulation gate failed: $($_.Exception.Message)"
    }
}
$PciePostPnrTimingDiagnosticCheckExists = Require-File `
    -Path $PciePostPnrTimingDiagnosticCheckPath `
    -Description 'PCIe S2-F negative-timing diagnostic gate'
if ($PciePostPnrTimingDiagnosticCheckExists) {
    try {
        & $PciePostPnrTimingDiagnosticCheckPath
    } catch {
        Add-Failure "PCIe S2-F negative-timing diagnostic gate failed: $($_.Exception.Message)"
    }
}
$PciePostSynDocExists = Require-File `
    -Path $PciePostSynDocPath `
    -Description 'PCIe S2-D post-synthesis smoke contract'
if ($PciePostSynDocExists) {
    $PciePostSynDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PciePostSynDocPath
    foreach ($Required in ([ordered]@{
            'PCIe S2-D canonical netlist' = 'pcie_dma_test_syn\.vm'
            'PCIe S2-D current run evidence' =
                '41135fd3fadd4c51a70508a6fa5af3e3'
            'PCIe S2-D success marker' = 'POST_SYN_RESET_PATH_OK'
            'PCIe S2-D PNR exclusion' = 'PNR'
            'PCIe S2-D SDF exclusion' = 'SDF'
        }).GetEnumerator()) {
        Require-Pattern -Text $PciePostSynDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PciePostPnrFuncDocExists = Require-File `
    -Path $PciePostPnrFuncDocPath `
    -Description 'PCIe S2-E post-PNR functional smoke contract'
if ($PciePostPnrFuncDocExists) {
    $PciePostPnrFuncDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PciePostPnrFuncDocPath
    foreach ($Required in ([ordered]@{
            'PCIe S2-E functional netlist' = 'pcie_dma_test_func\.v'
            'PCIe S2-E current run evidence' =
                '927abae8ed7d40aeb5d6f706b3723e0a'
            'PCIe S2-E success marker' = 'POST_PNR_FUNC_RESET_PATH_OK'
            'PCIe S2-E dynamic PASS evidence' = '`TEST PASS`'
            'PCIe S2-E SDF exclusion' = 'SDF'
            'PCIe S2-E board exclusion' = 'RK3568'
        }).GetEnumerator()) {
        Require-Pattern -Text $PciePostPnrFuncDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PciePostPnrTimingDocExists = Require-File `
    -Path $PciePostPnrTimingDocPath `
    -Description 'PCIe S2-F post-PNR timing blocker report'
if ($PciePostPnrTimingDocExists) {
    $PciePostPnrTimingDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PciePostPnrTimingDocPath
    foreach ($Required in ([ordered]@{
            'PCIe S2-F canonical timing netlist' = 'pcie_dma_test_sim\.v'
            'PCIe S2-F canonical SDF' = 'pcie_dma_test_sta\.sdf'
            'PCIe S2-F current run evidence' =
                '7fc77a7ec8db479db7332e8037426d6c'
            'PCIe S2-F SDF success evidence' =
                'SDF Backannotation Successfully Completed'
            'PCIe S2-F simulator error evidence' = 'Errors: 2'
            'PCIe S2-F model limitation evidence' = 'vsim-3004'
            'PCIe S2-F blocked status' = 'Status: blocked'
            'PCIe S2-F non-board boundary' = 'RK3568'
        }).GetEnumerator()) {
        Require-Pattern -Text $PciePostPnrTimingDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PciePostPnrTimingDiagnosticDocExists = Require-File `
    -Path $PciePostPnrTimingDiagnosticDocPath `
    -Description 'PCIe S2-F negative-timing diagnostic report'
if ($PciePostPnrTimingDiagnosticDocExists) {
    $PciePostPnrTimingDiagnosticDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PciePostPnrTimingDiagnosticDocPath
    foreach ($Required in ([ordered]@{
            'PCIe S2-F diagnostic run evidence' =
                'f79dc238c12949b7b67db2ef0d0ddd0b'
            'PCIe S2-F exact solver matrix' =
                'level1/level2/level3'
            'PCIe S2-F solver warning counts' =
                '3624/1590/1590'
            'PCIe S2-F model hash evidence' =
                'V_DRM18K_E1\.v.*9F35147248620F5C6FD7DE0077C2EF676DBE791CB283D98186BFAD2350834B43'
            'PCIe S2-F unchanged acceptance status' =
                'CanonicalAcceptanceChanged: false'
            'PCIe S2-F blocked diagnostic status' =
                'AcceptanceStatus: blocked'
        }).GetEnumerator()) {
        Require-Pattern -Text $PciePostPnrTimingDiagnosticDocText `
            -Pattern $Required.Value -Description $Required.Key | Out-Null
    }
}
$PcieS2aDocExists = Require-File `
    -Path $PcieS2aDocPath `
    -Description 'PCIe S2-A behavior smoke contract'
if ($PcieS2aDocExists) {
    $PcieS2aDocText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieS2aDocPath
    foreach ($Required in ([ordered]@{
            'PCIe S2-A controlled-model boundary' = 'model-controlled link'
            'PCIe S2-B real-link boundary' = 'S2-B'
            'PCIe S2-C DMA boundary' = 'S2-C'
            'PCIe S2-A Questa version evidence' = 'Questa Sim-64\s+`2021\.1`'
            'PCIe S2-A current dynamic run evidence' =
                '966942334060436dba8444ae9155557c'
            'PCIe S2-A dynamic PASS evidence' = '`TEST PASS`'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieS2aDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PcieS2bDocExists = Require-File `
    -Path $PcieS2bDocPath `
    -Description 'PCIe S2-B real-link contract'
if ($PcieS2bDocExists) {
    $PcieS2bDocText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieS2bDocPath
    foreach ($Required in ([ordered]@{
            'PCIe S2-B real RC role' = 'pango_pcie_top_sim'
            'PCIe S2-B real EP role' = 'pcie_dma_test'
            'PCIe S2-B Questa version evidence' = 'Questa Sim-64\s+`2021\.1`'
            'PCIe S2-B current dynamic run evidence' =
                '30bad6e164be4a4b8284a00f1e96bd87'
            'PCIe S2-B dynamic link marker' = 'S2B_REAL_LINK_UP'
            'PCIe S2-B dynamic PASS evidence' = '`TEST PASS`'
            'PCIe S2-B non-board boundary' = 'RK3568'
        }).GetEnumerator()) {
        Require-Pattern -Text $PcieS2bDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
$PcieReadmePath = Join-Path $RepoRoot 'pcie_dma_test_100h\README.md'
if (Test-Path -LiteralPath $PcieReadmePath -PathType Leaf) {
    $PcieReadmeText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieReadmePath
    Require-Pattern -Text $PcieReadmeText -Pattern 'H2B_BASELINE_GATE\.md' `
        -Description 'PCIe README H2-B0 gate link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'H2-B1' `
        -Description 'PCIe README H2-B1 boundary' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'CI8A_BUILD_PROVENANCE\.md' `
        -Description 'PCIe README CI-8A provenance link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'S2A_BEHAVIOR_SMOKE\.md' `
        -Description 'PCIe README S2-A behavior smoke link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'S2B_REAL_LINK\.md' `
        -Description 'PCIe README S2-B real-link link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'S2D_POST_SYN_SMOKE\.md' `
        -Description 'PCIe README S2-D post-synthesis smoke link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'S2E_POST_PNR_FUNC_SMOKE\.md' `
        -Description 'PCIe README S2-E post-PNR functional smoke link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'S2F_POST_PNR_TIMING_SMOKE\.md' `
        -Description 'PCIe README S2-F post-PNR timing blocker link' | Out-Null
    Require-Pattern -Text $PcieReadmeText -Pattern 'S2F_NEGATIVE_TIMING_DIAGNOSTIC\.md' `
        -Description 'PCIe README S2-F negative-timing diagnostic link' | Out-Null
}
$PcieEvidencePath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\PCIE_BOARD_EVIDENCE.md'
if (Test-Path -LiteralPath $PcieEvidencePath -PathType Leaf) {
    $PcieEvidenceText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $PcieEvidencePath
    Require-Pattern -Text $PcieEvidenceText `
        -Pattern 'H2B_BASELINE_FINGERPRINT\.json' `
        -Description 'PCIe board evidence H2-B0 fingerprint link' | Out-Null
    Require-Pattern -Text $PcieEvidenceText -Pattern 'H2-B1' `
        -Description 'PCIe board evidence H2-B1 boundary' | Out-Null
}

$PowerShellScripts = @(Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -Filter '*.ps1' |
    Where-Object { $_.FullName -notmatch '[\\/]build[\\/]' -and $_.FullName -notmatch '[\\/]\.git[\\/]' })
foreach ($Script in $PowerShellScripts) {
    $ParseTokens = $null
    $ParseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $Script.FullName,
        [ref]$ParseTokens,
        [ref]$ParseErrors) | Out-Null
    if ($ParseErrors.Count -gt 0) {
        $Details = ($ParseErrors | ForEach-Object { "line $($_.Extent.StartLineNumber): $($_.Message)" }) -join '; '
        Add-Failure "PowerShell parse failed for $($Script.FullName): $Details"
    } else {
        Write-Host "INFO: PowerShell AST passed: $($Script.FullName)"
    }
}

$Ddr3CorePath = Join-Path $RepoRoot 'ddr3_test\ddr3_test\ip_core\ddr3\ddr3.v'
$Ddr3WrapperPath = Join-Path $RepoRoot 'ddr3_test\ddr3_test\ip_core\ddr3\example_design\rtl\test_ddr.v'
$Ddr3PortMapPath = Join-Path $RepoRoot 'ddr3_test\ddr3_test\doc\D3A_PORT_MAP.md'
$Ddr3CoreExists = Require-File -Path $Ddr3CorePath -Description 'DDR3 core source for D3-0-R gate'
$Ddr3WrapperExists = Require-File -Path $Ddr3WrapperPath -Description 'DDR3 wrapper source for D3-0-R gate'
$Ddr3PortMapExists = Require-File -Path $Ddr3PortMapPath -Description 'DDR3 D3-A port map'
if ($Ddr3CoreExists -and $Ddr3WrapperExists -and $Ddr3PortMapExists) {
    $Ddr3CoreText = Get-Content -Raw -Encoding UTF8 -LiteralPath $Ddr3CorePath
    $Ddr3WrapperText = Get-Content -Raw -Encoding UTF8 -LiteralPath $Ddr3WrapperPath
    $Ddr3PortMapText = Get-Content -Raw -Encoding UTF8 -LiteralPath $Ddr3PortMapPath

    Require-Pattern -Text $Ddr3CoreText -Pattern '(?m)^module\s+ddr3\b' `
        -Description 'DDR3 core module declaration' | Out-Null
    foreach ($Pattern in @(
            'parameter\s+MEM_ROW_WIDTH\s*=\s*15',
            'parameter\s+MEM_COLUMN_WIDTH\s*=\s*10',
            'parameter\s+MEM_BANK_WIDTH\s*=\s*3',
            'parameter\s+MEM_DQ_WIDTH\s*=\s*16',
            'parameter\s+MEM_DQS_WIDTH\s*=\s*2',
            'axi_wdata',
            'axi_rdata',
            'ddr_init_done',
            'core_clk')) {
        Require-Pattern -Text $Ddr3CoreText -Pattern $Pattern `
            -Description "DDR3 core contract pattern '$Pattern'" | Out-Null
    }
    if ($Ddr3CoreText -match '(?i)axi_rready') {
        Add-Failure 'DDR3 core unexpectedly declares axi_rready; D3-0-R contract must be re-reviewed'
    }

    foreach ($Pattern in @('(?m)^module\s+test_ddr\b', 'I_ips_ddr_top', '\.ddr_init_done', '\.core_clk', '\.axi_wready')) {
        Require-Pattern -Text $Ddr3WrapperText -Pattern $Pattern `
            -Description "DDR3 wrapper contract pattern '$Pattern'" | Out-Null
    }
    foreach ($Pattern in @('CTRL_ADDR_WIDTH', '128', 'I_ips_ddr_top', 'axi_wready', 'axi_rvalid', 'axi_rready', 'byte/word')) {
        Require-Pattern -Text $Ddr3PortMapText -Pattern ([regex]::Escape($Pattern)) `
            -Description "DDR3 port map evidence '$Pattern'" | Out-Null
    }
}

if ($Failures.Count -gt 0) {
    Write-Error ("Repository consistency gate failed with {0} issue(s):`n- {1}" -f `
        $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host 'INFO: repository consistency gate passed'
exit 0
