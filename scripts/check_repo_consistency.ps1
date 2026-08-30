param(
    [string]$RepoRoot,
    [string]$PdsTclInventoryPath
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
$ApprovedBoard = 'RK3568+PG2L50H100H'
$ApprovedFpgaPart = 'PG2L50H-6IFBG484'
$ApprovedPdsDevice = 'PG2L50H'
$Ddr3RegeneratePath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\scripts\regenerate_ip.ps1'
$Ddr3RegenerationDocPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\doc\M2_IP_REGENERATION.md'
$Ddr3M2B1AuditPath = Join-Path $RepoRoot `
    'ddr3_test\ddr3_test\doc\M2B1_PARAMETER_AND_DIFF_AUDIT.md'
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
    -Description 'DDR3 PG2L50H staging regeneration entry'
$Ddr3RegenerationDocExists = Require-File -Path $Ddr3RegenerationDocPath `
    -Description 'DDR3 M2 IP regeneration audit'
$Ddr3M2B1AuditExists = Require-File -Path $Ddr3M2B1AuditPath `
    -Description 'DDR3 M2-B1 parameter and diff audit'
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
            'M2 approved FPGA part' = [regex]::Escape($ApprovedFpgaPart)
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

# M3-A is an audit-only gate. Protect the four active IDFs until the reviewed
# PG2L50H staging set is promoted atomically in a later batch.
$OvM3AuditExists = Require-File -Path $OvM3AuditPath `
    -Description 'OV7725 M3-A four-IP migration audit'
if ($OvM3AuditExists) {
    $OvM3AuditText = Get-Content -Raw -Encoding UTF8 -LiteralPath $OvM3AuditPath
    foreach ($Required in ([ordered]@{
            'M3-A approved FPGA part' = [regex]::Escape($ApprovedFpgaPart)
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
            Add-Failure "OV7725 canonical IP changed before M3 promotion: $($Entry.Key)"
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
    Require-Pattern -Text $MatrixText -Pattern 'OV7725 HDMI' `
        -Description 'simulation matrix OV7725 coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'DDR3' `
        -Description 'simulation matrix DDR3 coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'PCIe DMA' `
        -Description 'simulation matrix PCIe coverage' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S1 DDR3' `
        -Description 'simulation matrix S1 DDR3 queue' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S2 PCIe' `
        -Description 'simulation matrix S2 PCIe queue' | Out-Null
    Require-Pattern -Text $MatrixText -Pattern 'S3 OV7725' `
        -Description 'simulation matrix S3 OV7725 queue' | Out-Null
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
        Require-Pattern -Text $ReadmeText -Pattern '(?i)仿真|ModelSim|QuestaSim' `
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

# The active PCIe IP already matches the approved physical FPGA. Parse the IDF
# structurally so future edits cannot silently restore the rejected 100H target.
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
