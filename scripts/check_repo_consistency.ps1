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
$PdsTclInventoryDocPath = Join-Path $RepoRoot `
    'docs\PDS_TCL_ENTRYPOINT_INVENTORY.md'
if ([string]::IsNullOrWhiteSpace($PdsTclInventoryPath)) {
    $PdsTclInventoryPath = Join-Path $RepoRoot `
        'docs\PDS_TCL_ENTRYPOINT_INVENTORY.json'
}
$PdsTclGatePath = Join-Path $RepoRoot 'scripts\check_pds_tcl_entrypoints.ps1'
$SensitiveDiffGatePath = Join-Path $RepoRoot 'scripts\check_sensitive_diff.ps1'
$SensitiveDiffGateDocPath = Join-Path $RepoRoot 'docs\SENSITIVE_DIFF_GATE.md'
$GitAttributesPath = Join-Path $RepoRoot '.gitattributes'
$Ov5640ScopePath = Join-Path $RepoRoot 'docs\OV5640_TARGET_SCOPE.md'
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
$PcieS2bDocPath = Join-Path $RepoRoot `
    'pcie_dma_test_100h\doc\S2B_REAL_LINK.md'
$ApprovedBoard = 'RK3568_MES2L100H'
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
            'approved FPGA target' = 'PG2L100H-6IFBG484'
            'reference import boundary' = '59_top_dual_ov5640_hdmi'
            'Questa validation requirement' = 'Questa.*2021\.1'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ov5640ScopeText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
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

$Ddr3RegenerateExists = Require-File -Path $Ddr3RegeneratePath `
    -Description 'blocked legacy DDR3 PG2L50H probe'
$Ddr3RegenerationDocExists = Require-File -Path $Ddr3RegenerationDocPath `
    -Description 'DDR3 M2 IP regeneration audit'
$Ddr3M2B1AuditExists = Require-File -Path $Ddr3M2B1AuditPath `
    -Description 'DDR3 M2-B1 parameter and diff audit'
if ($Ddr3RegenerateExists) {
    $Ddr3RegenerateText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3RegeneratePath
    foreach ($Required in ([ordered]@{
            'legacy probe immediate execution block' = '(?m)^throw\s+''[^'']*PG2L50H[^'']*PG2L100H[^'']*blocked[^'']*''\s*$'
            'legacy PDS IP generator body retained for audit' = 'ip_generate\.exe'
            'legacy staging constrained under build directory' = "'build'"
            'legacy canonical hash preservation gate retained' = 'Get-FileHash'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3RegenerateText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($Ddr3RegenerationDocExists) {
    $Ddr3RegenerationDocText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3RegenerationDocPath
    foreach ($Required in ([ordered]@{
            'M2 approved FPGA part' = [regex]::Escape($ApprovedFpgaPart)
            'M2 approved PDS target' = 'Logos2\s*/\s*PG2L100H\s*/\s*FBG484\s*/\s*-6'
            'M2 legacy probe rejection' = 'scripts/regenerate_ip\.ps1.*\u4e0d\u80fd\u6267\u884c'
            'M2 PG2L100H staging path' = 'build/ipgen/pg2l100h'
            'M2 canonical hash preservation' = 'SHA-256 \u4e0d\u53d8'
            'M2 no manual IDF edits' = '\u7981\u6b62\u624b\u6539.*<version>.*<device>'
            'M2 pre-generation evidence section' = '(?m)^##\s+3\.\s+\u751f\u6210\u524d\u8d44\u6599\s*\r?$'
            'M2 post-generation verification section' = '(?m)^##\s+4\.\s+\u751f\u6210\u540e\u6838\u9a8c\s*\r?$'
            'M2 promotion review boundary' = '\u624d\u5141\u8bb8\u8fdb\u5165 D3-A \u548c canonical \u5347\u683c\u8bc4\u5ba1'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3RegenerationDocText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}
if ($Ddr3M2B1AuditExists) {
    $Ddr3M2B1AuditText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $Ddr3M2B1AuditPath
    foreach ($Required in ([ordered]@{
            'M2-B1 approved FPGA part' = [regex]::Escape($ApprovedFpgaPart)
            'M2-B1 active PG2L100H header' = '\u6d3b\u52a8 DDR3 IP \u7684\u76ee\u6807 header \u5df2\u662f PG2L100H'
            'M2-B1 hidden derived parameter review' = 'DEVICE_100H_EN.*\u6d3e\u751f\u503c'
            'M2-B1 PG2L100H staging path' = 'build/ipgen/pg2l100h'
            'M2-B1 current staging acceptance section' = '(?m)^##\s+4\.\s+\u5f53\u524d PG2L100H staging \u9a8c\u6536\s*\r?$'
            'M2-B1 canonical hash preservation' = 'SHA-256.*\u4fdd\u6301\u4e0d\u53d8'
            'M2-B1 promotion threshold section' = '(?m)^##\s+5\.\s+\u5347\u683c\u95e8\u69db\s*\r?$'
            'M2-B1 legacy 50H rejection' = '\u5386\u53f2 50H \u8d44\u4ea7.*PG2L100H \u901a\u8fc7\u8bc1\u636e'
        }).GetEnumerator()) {
        Require-Pattern -Text $Ddr3M2B1AuditText -Pattern $Required.Value `
            -Description $Required.Key | Out-Null
    }
}

$RootReadmePath = Join-Path $RepoRoot 'README.md'
$TodoPath = Join-Path $RepoRoot 'TODO.md'
$MatrixExists = Require-File -Path $MatrixPath -Description 'simulation readiness matrix'
if ($MatrixExists) {
    $MatrixText = Get-Content -Raw -Encoding UTF8 -LiteralPath $MatrixPath
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
    Require-Pattern -Text $MatrixText -Pattern 'S3 OV5640' `
        -Description 'simulation matrix S3 OV5640 queue' | Out-Null
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
}

$IgnoreText = Get-Content -Raw -LiteralPath (Join-Path $RepoRoot '.gitignore')
# Accept both LF and CRLF checkouts for the required generated-output rule.
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

# The active PCIe IP must match the approved current physical FPGA. Parse the
# IDF structurally so an old PG2L50H asset cannot silently pass as 100H.
$PcieIdfPath = Join-Path $RepoRoot 'pcie_dma_test_100h\ipcore\pcie_test\pcie_test.idf'
if (Require-File -Path $PcieIdfPath -Description 'active PCIe IP definition') {
    try {
        [xml]$PcieIdfXml = Get-Content -Raw -Encoding UTF8 -LiteralPath $PcieIdfPath
        $PcieIdfDevice = [string]$PcieIdfXml.ip_inst.header.device
        if ($PcieIdfDevice -ne $ApprovedPdsDevice) {
            Add-Failure "PCIe IP targets '$PcieIdfDevice'; approved device is '$ApprovedPdsDevice'"
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
        foreach ($Field in ([ordered]@{
                family = $ApprovedPdsFamily
                device = $ApprovedPdsDevice
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
            'PCIe CI-8A seven-artifact contract' = '\u4e03\u9879\u6700\u7ec8\u8bc1\u636e'
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
            'PCIe S2-A dynamic run evidence' = 'fab4ccef3e2445abbd9d1cad1e66b2ab'
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
            'PCIe S2-B dynamic blocker' = 'vsim\.exe'
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
