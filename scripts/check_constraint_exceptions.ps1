param(
    [string]$RepoRoot,
    [string]$InventoryPath,
    [switch]$SelfTest
)

# Verify exact text provenance for timing exceptions and the dedicated-clock
# route override. This gate does not prove that PDS resolves the objects or
# that any exception is technically justified.
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

if ([string]::IsNullOrWhiteSpace($InventoryPath)) {
    $InventoryPath = Join-Path $RepoRoot 'docs\CONSTRAINT_EXCEPTION_INVENTORY.json'
}
$InventoryPath = (Resolve-Path -LiteralPath $InventoryPath).Path

function Get-CommandKind {
    param([Parameter(Mandatory)][string]$Command)

    if ($Command -match '^set_multicycle_path\b') {
        return 'set_multicycle_path'
    }
    if ($Command -match '^set_clock_groups\b') {
        return 'set_clock_groups'
    }
    if ($Command -match '^set_false_path\b') {
        return 'set_false_path'
    }
    if ($Command -match '^set_max_delay\b') {
        return 'set_max_delay'
    }
    if ($Command -match '^set_min_delay\b') {
        return 'set_min_delay'
    }
    if ($Command -match '^set_disable_timing\b') {
        return 'set_disable_timing'
    }
    if ($Command -match '^define_attribute\b.*\{PAP_CLOCK_DEDICATED_ROUTE\}') {
        return 'pap_clock_dedicated_route'
    }
    return $null
}

function Get-ConstraintCommands {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[string]]$Failures
    )

    $Records = [System.Collections.Generic.List[object]]::new()
    $LineNumber = 0
    foreach ($Line in Get-Content -LiteralPath $Path) {
        $LineNumber++
        $Normalized = $Line.Trim().TrimEnd("`r")
        if ([string]::IsNullOrWhiteSpace($Normalized) -or
            $Normalized.StartsWith('#')) {
            continue
        }

        if ($Normalized -match '^source(?:\s|$)') {
            $Failures.Add("unsupported sourced constraint at ${Path}:$LineNumber")
            continue
        }

        $Kind = Get-CommandKind -Command $Normalized
        $ContainsRelevantToken = $Normalized -match
            '(?:set_(?:multicycle_path|clock_groups|false_path|max_delay|min_delay|disable_timing)\b|PAP_CLOCK_DEDICATED_ROUTE)'
        if ($null -eq $Kind) {
            if ($ContainsRelevantToken) {
                $Failures.Add("unsupported embedded constraint command at ${Path}:$LineNumber")
            }
            continue
        }

        if ($Normalized -match '\\$') {
            $Failures.Add("unsupported Tcl continuation at ${Path}:$LineNumber")
            continue
        }
        if ($Normalized.Contains(';')) {
            $Failures.Add("unsupported Tcl multi-command line at ${Path}:$LineNumber")
            continue
        }

        $Records.Add([pscustomobject]@{
                line = $LineNumber
                kind = $Kind
                normalized_command = $Normalized
            })
    }
    return @($Records)
}

function Get-RecordKey {
    param(
        [Parameter(Mandatory)][string]$Kind,
        [Parameter(Mandatory)][string]$Command
    )

    return "$Kind`n$Command"
}

function Get-NormalizedSha256 {
    param([Parameter(Mandatory)][string]$Path)

    $Utf8 = [System.Text.UTF8Encoding]::new($false, $true)
    $Text = $Utf8.GetString([System.IO.File]::ReadAllBytes($Path))
    $Normalized = $Text.Replace("`r`n", "`n").Replace("`r", "`n")
    $Bytes = $Utf8.GetBytes($Normalized)
    $Hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString(
                $Hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $Hasher.Dispose()
    }
}

function Get-Multiset {
    param([Parameter(Mandatory)][object[]]$Records)

    $Counts = @{}
    foreach ($Record in $Records) {
        $Key = Get-RecordKey -Kind $Record.kind -Command $Record.normalized_command
        if ($Counts.ContainsKey($Key)) {
            $Counts[$Key]++
        } else {
            $Counts[$Key] = 1
        }
    }
    return $Counts
}

function Test-InventoryState {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)]$Inventory,
        [switch]$CheckGitBlob
    )

    $Failures = [System.Collections.Generic.List[string]]::new()
    if ($Inventory.schema_version -ne 1) {
        $Failures.Add("unsupported inventory schema version: $($Inventory.schema_version)")
    }

    $ActualTimingCount = 0
    $ActualOverrideCount = 0
    foreach ($Artifact in $Inventory.artifacts) {
        if ($Artifact.artifact_role -eq 'not_created') {
            if ($Artifact.commands.Count -ne 0) {
                $Failures.Add("not-created project $($Artifact.project) must have zero commands")
            }

            $ProductRoot = Join-Path $Root ($Artifact.project_root -replace '/', '\')
            if (-not (Test-Path -LiteralPath $ProductRoot -PathType Container)) {
                $Failures.Add("not-created project documentation root is missing: $ProductRoot")
                continue
            }

            $PrematureConstraints = @(Get-ChildItem -LiteralPath $ProductRoot -Recurse -File |
                Where-Object { $_.Extension -in @('.fdc', '.sdc', '.pcf', '.pds') })
            foreach ($File in $PrematureConstraints) {
                $Failures.Add("premature dual-OV5640 constraint/project file: $($File.FullName)")
            }
            foreach ($RelativePath in $Artifact.required_absent_paths) {
                $Candidate = Join-Path $Root ($RelativePath -replace '/', '\')
                if (Test-Path -LiteralPath $Candidate) {
                    $Failures.Add("premature dual-OV5640 build entry: $Candidate")
                }
            }
            continue
        }

        $ConstraintPath = Join-Path $Root ($Artifact.path -replace '/', '\')
        if (-not (Test-Path -LiteralPath $ConstraintPath -PathType Leaf)) {
            $Failures.Add("constraint artifact is missing: $ConstraintPath")
            continue
        }

        try {
            $ActualSha = Get-NormalizedSha256 -Path $ConstraintPath
        } catch {
            $Failures.Add("constraint is not strict UTF-8: $($Artifact.path)")
            $ActualSha = $null
        }
        if ($ActualSha -ne $Artifact.normalized_sha256) {
            $Failures.Add("normalized SHA-256 drift for $($Artifact.path)")
        }

        if ($CheckGitBlob) {
            $IndexRecord = (& git -C $Root ls-files -s -- $Artifact.path).Trim()
            $BlobMatch = [regex]::Match(
                $IndexRecord,
                '^\d+\s+([0-9a-fA-F]{40,64})\s+\d+\s+')
            if (-not $BlobMatch.Success -or
                $BlobMatch.Groups[1].Value.ToLowerInvariant() -ne
                $Artifact.blob_oid) {
                $Failures.Add("Git index blob drift for $($Artifact.path)")
            }
        }

        foreach ($Entrypoint in $Artifact.entrypoints) {
            $EntrypointPath = Join-Path $Root ($Entrypoint.path -replace '/', '\')
            if (-not (Test-Path -LiteralPath $EntrypointPath -PathType Leaf)) {
                $Failures.Add("constraint entrypoint is missing: $EntrypointPath")
                continue
            }
            $EntrypointText = Get-Content -LiteralPath $EntrypointPath -Raw
            if (-not $EntrypointText.Contains($Entrypoint.required_text)) {
                $Failures.Add("constraint entrypoint no longer references $($Artifact.path)")
            }
        }

        $ActualRecords = @(Get-ConstraintCommands -Path $ConstraintPath -Failures $Failures)
        $ExpectedRecords = @($Artifact.commands)
        $ActualSet = Get-Multiset -Records $ActualRecords
        $ExpectedSet = Get-Multiset -Records $ExpectedRecords

        $AllKeys = @($ActualSet.Keys + $ExpectedSet.Keys | Sort-Object -Unique)
        foreach ($Key in $AllKeys) {
            $ActualCount = if ($ActualSet.ContainsKey($Key)) { $ActualSet[$Key] } else { 0 }
            $ExpectedCount = if ($ExpectedSet.ContainsKey($Key)) { $ExpectedSet[$Key] } else { 0 }
            if ($ActualCount -ne $ExpectedCount) {
                $DisplayKey = $Key -replace "`n", ': '
                $Failures.Add(
                    "constraint command drift in $($Artifact.path): $DisplayKey " +
                    "expected=$ExpectedCount actual=$ActualCount")
            }
        }

        foreach ($Expected in $ExpectedRecords) {
            foreach ($Field in @('object', 'reason', 'basis', 'review_status')) {
                if ([string]::IsNullOrWhiteSpace([string]$Expected.$Field)) {
                    $Failures.Add("missing $Field for $($Artifact.project) line $($Expected.line)")
                }
            }

            if ($Expected.kind -eq 'pap_clock_dedicated_route') {
                $ActualOverrideCount++
            } else {
                $ActualTimingCount++
            }
        }
    }

    if ($ActualTimingCount -ne $Inventory.summary.timing_exception_count) {
        $Failures.Add(
            "timing exception summary mismatch: expected " +
            "$($Inventory.summary.timing_exception_count), inventory has $ActualTimingCount")
    }
    if ($ActualOverrideCount -ne $Inventory.summary.dedicated_route_override_count) {
        $Failures.Add(
            "dedicated-route summary mismatch: expected " +
            "$($Inventory.summary.dedicated_route_override_count), inventory has $ActualOverrideCount")
    }

    return @($Failures)
}

function New-SelfTestFixture {
    param(
        [Parameter(Mandatory)][string]$SourceRoot,
        [Parameter(Mandatory)]$Inventory,
        [Parameter(Mandatory)][string]$FixtureRoot
    )

    foreach ($Artifact in $Inventory.artifacts) {
        if ($Artifact.artifact_role -eq 'not_created') {
            $ProductRoot = Join-Path $FixtureRoot ($Artifact.project_root -replace '/', '\')
            New-Item -ItemType Directory -Force -Path $ProductRoot | Out-Null
            continue
        }

        foreach ($RelativePath in @($Artifact.path) + @($Artifact.entrypoints.path)) {
            $SourcePath = Join-Path $SourceRoot ($RelativePath -replace '/', '\')
            $TargetPath = Join-Path $FixtureRoot ($RelativePath -replace '/', '\')
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TargetPath) |
                Out-Null
            Copy-Item -LiteralPath $SourcePath -Destination $TargetPath
        }
    }
}

$Inventory = Get-Content -LiteralPath $InventoryPath -Raw | ConvertFrom-Json -Depth 100
$BaselineFailures = @(Test-InventoryState -Root $RepoRoot -Inventory $Inventory -CheckGitBlob)
if ($BaselineFailures.Count -ne 0) {
    foreach ($Failure in $BaselineFailures) {
        Write-Error $Failure
    }
    exit 1
}

if ($SelfTest) {
    $TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
        'pds-constraint-gate-' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
        $AddedFixture = Join-Path $TempRoot 'added'
        $ChangedFixture = Join-Path $TempRoot 'changed'
        $CameraFixture = Join-Path $TempRoot 'camera'
        $CrlfFixture = Join-Path $TempRoot 'crlf'
        $ParserFixture = Join-Path $TempRoot 'parser'
        New-SelfTestFixture -SourceRoot $RepoRoot -Inventory $Inventory `
            -FixtureRoot $CrlfFixture
        foreach ($Artifact in $Inventory.artifacts) {
            if ($Artifact.artifact_role -eq 'not_created') {
                continue
            }
            $CrlfPath = Join-Path $CrlfFixture ($Artifact.path -replace '/', '\')
            $Text = [System.IO.File]::ReadAllText($CrlfPath).
                Replace("`r`n", "`n").Replace("`r", "`n").Replace("`n", "`r`n")
            [System.IO.File]::WriteAllText(
                $CrlfPath,
                $Text,
                [System.Text.UTF8Encoding]::new($false))
        }
        $CrlfFailures = @(
            Test-InventoryState -Root $CrlfFixture -Inventory $Inventory)
        if ($CrlfFailures.Count -ne 0) {
            throw 'self-test failed: CRLF-only checkout drift was rejected'
        }

        New-SelfTestFixture -SourceRoot $RepoRoot -Inventory $Inventory `
            -FixtureRoot $AddedFixture

        $DdrPath = Join-Path $AddedFixture (
            'ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr_test.fdc' -replace '/', '\')
        [System.IO.File]::AppendAllText(
            $DdrPath,
            "`r`nset_false_path -from [get_clocks probe_a] -to [get_clocks probe_b]`r`n")
        $AddedFailures = @(
            Test-InventoryState -Root $AddedFixture -Inventory $Inventory)
        if (-not ($AddedFailures -match 'constraint command drift')) {
            throw 'self-test failed: unregistered exception command drift was not detected'
        }

        New-SelfTestFixture -SourceRoot $RepoRoot -Inventory $Inventory `
            -FixtureRoot $ChangedFixture
        $PciePath = Join-Path $ChangedFixture (
            'pcie_dma_test_100h/fdc/pcie_dma_test.fdc' -replace '/', '\')
        $PcieText = [System.IO.File]::ReadAllText($PciePath)
        $PcieText = $PcieText.Replace(
            'set_clock_groups -name group_1',
            'set_clock_groups -name changed_group')
        [System.IO.File]::WriteAllText($PciePath, $PcieText)
        $ChangedFailures = @(
            Test-InventoryState -Root $ChangedFixture -Inventory $Inventory)
        if (-not ($ChangedFailures -match 'constraint command drift')) {
            throw 'self-test failed: changed exception command drift was not detected'
        }

        New-SelfTestFixture -SourceRoot $RepoRoot -Inventory $Inventory `
            -FixtureRoot $CameraFixture
        $PrematureFdc = Join-Path $CameraFixture `
            '59_top_dual_ov5640_hdmi\constraints\top.fdc'
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $PrematureFdc) |
            Out-Null
        [System.IO.File]::WriteAllText($PrematureFdc, 'set_false_path -from A -to B')
        $CameraFailures = @(
            Test-InventoryState -Root $CameraFixture -Inventory $Inventory)
        if (-not ($CameraFailures -match
                'premature dual-OV5640 constraint/project file')) {
            throw 'self-test failed: premature dual-OV5640 FDC was not detected'
        }

        New-SelfTestFixture -SourceRoot $RepoRoot -Inventory $Inventory `
            -FixtureRoot $ParserFixture
        $ParserFdc = Join-Path $ParserFixture (
            'ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr_test.fdc' -replace '/', '\')
        [System.IO.File]::AppendAllText(
            $ParserFdc,
            "`r`nsource extra.fdc" +
            "`r`nset_false_path -from A -to B \" +
            "`r`n  -through C" +
            "`r`nset_clock_groups -asynchronous -group A; set_false_path -from B -to C`r`n")
        $ParserFailures = @(
            Test-InventoryState -Root $ParserFixture -Inventory $Inventory)
        foreach ($ExpectedFailure in @(
                'unsupported sourced constraint',
                'unsupported Tcl continuation',
                'unsupported Tcl multi-command line'
            )) {
            if (-not ($ParserFailures -match $ExpectedFailure)) {
                throw "self-test failed: missing parser failure '$ExpectedFailure'"
            }
        }

        Write-Host 'INFO: constraint exception portability and negative self-tests passed'
    } finally {
        $ResolvedTemp = [System.IO.Path]::GetFullPath($TempRoot)
        $SystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if ($ResolvedTemp.StartsWith($SystemTemp, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Test-Path -LiteralPath $ResolvedTemp)) {
            Remove-Item -LiteralPath $ResolvedTemp -Recurse -Force
        }
    }
}

Write-Host (
    'INFO: constraint exception inventory passed: ' +
    "$($Inventory.summary.timing_exception_count) timing exception(s), " +
    "$($Inventory.summary.dedicated_route_override_count) dedicated-route override(s)")
exit 0
