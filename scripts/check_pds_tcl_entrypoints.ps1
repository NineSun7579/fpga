param(
    [string]$RepoRoot,
    [string]$InventoryPath
)

# Classify every tracked Tcl file so historical and vendor-generated scripts
# cannot be mistaken for the project-owned PG2L100H build entries.
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

if ([string]::IsNullOrWhiteSpace($InventoryPath)) {
    $InventoryPath = Join-Path $RepoRoot 'docs\PDS_TCL_ENTRYPOINT_INVENTORY.json'
} elseif (-not [System.IO.Path]::IsPathRooted($InventoryPath)) {
    $InventoryPath = Join-Path $RepoRoot $InventoryPath
}

$Failures = [System.Collections.Generic.List[string]]::new()
$AllowedRoles = @(
    'canonical_project_build',
    'migration_blocked_project_build',
    'canonical_support_tool',
    'historical_gui',
    'vendor_generated_internal',
    'vendor_sim_internal'
)

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)
    $Failures.Add($Message)
}

function Get-TclFacts {
    param([Parameter(Mandatory)][string]$Path)

    $Text = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path
    $Devices = @(
        [regex]::Matches(
            $Text,
            '(?m)^\s*(?:set_arch\b[^\r\n]*?-device|-device)\s+([^\s\\]+)') |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -CaseSensitive -Unique
    )

    return [pscustomobject]@{
        SetArchCount = [regex]::Matches($Text, '(?m)^\s*set_arch\b').Count
        Devices = $Devices
        ContainsAbsolutePaths = [regex]::IsMatch(
            $Text,
            '(?i)(?:\b[A-Z]:[\\/]|\\\\)')
    }
}

if (-not (Test-Path -LiteralPath $InventoryPath -PathType Leaf)) {
    Write-Error "PDS Tcl inventory not found: $InventoryPath"
    exit 1
}

try {
    $Inventory = Get-Content -Raw -Encoding UTF8 -LiteralPath $InventoryPath |
        ConvertFrom-Json
} catch {
    Write-Error "PDS Tcl inventory is not valid JSON: $InventoryPath"
    exit 1
}

if ($Inventory.schema_version -ne 1) {
    Add-Failure "Unsupported PDS Tcl inventory schema: $($Inventory.schema_version)"
}

$Entries = @($Inventory.entries)
$DuplicatePaths = @($Entries | Group-Object -Property path | Where-Object Count -gt 1)
foreach ($Duplicate in $DuplicatePaths) {
    Add-Failure "Duplicate PDS Tcl inventory path: $($Duplicate.Name)"
}

$TrackedTcl = @(git -C $RepoRoot ls-files -- '*.tcl')
if ($LASTEXITCODE -ne 0) {
    Write-Error 'git ls-files failed while enumerating tracked Tcl files'
    exit 1
}
$TrackedTcl = @($TrackedTcl | Sort-Object -CaseSensitive -Unique)
$InventoryPaths = @(
    $Entries |
        ForEach-Object { ([string]$_.path) -replace '\\', '/' } |
        Sort-Object -CaseSensitive -Unique
)

foreach ($Difference in @(Compare-Object -ReferenceObject $TrackedTcl `
        -DifferenceObject $InventoryPaths -CaseSensitive)) {
    if ($Difference.SideIndicator -eq '<=') {
        Add-Failure "Tracked Tcl is not classified: $($Difference.InputObject)"
    } else {
        Add-Failure "Inventory entry is not a tracked Tcl file: $($Difference.InputObject)"
    }
}

foreach ($Entry in $Entries) {
    $RelativePath = ([string]$Entry.path) -replace '\\', '/'
    $Role = [string]$Entry.role
    if ($AllowedRoles -notcontains $Role) {
        Add-Failure "Unsupported role '$Role' for $RelativePath"
        continue
    }

    $FullPath = Join-Path $RepoRoot ($RelativePath -replace '/', '\\')
    if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
        continue
    }

    $Facts = Get-TclFacts -Path $FullPath
    if ($Facts.SetArchCount -ne [int]$Entry.set_arch_count) {
        Add-Failure ("set_arch count changed for {0}: expected {1}, actual {2}" -f `
                $RelativePath, $Entry.set_arch_count, $Facts.SetArchCount)
    }

    $ExpectedDevices = @(
        @($Entry.devices) |
            ForEach-Object { [string]$_ } |
            Sort-Object -CaseSensitive -Unique
    )
    $DeviceDifference = @(Compare-Object -ReferenceObject $ExpectedDevices `
            -DifferenceObject $Facts.Devices -CaseSensitive)
    if ($DeviceDifference.Count -gt 0) {
        Add-Failure ("set_arch devices changed for {0}: expected [{1}], actual [{2}]" -f `
                $RelativePath, ($ExpectedDevices -join ', '), ($Facts.Devices -join ', '))
    }

    if ($Facts.ContainsAbsolutePaths -ne [bool]$Entry.contains_absolute_paths) {
        Add-Failure ("absolute-path fact changed for {0}: expected {1}, actual {2}" -f `
                $RelativePath, $Entry.contains_absolute_paths, $Facts.ContainsAbsolutePaths)
    }

    $IsRunEntry = [bool]$Entry.run_ps1_entry
    if ($IsRunEntry -and $Role -notin @(
            'canonical_project_build',
            'migration_blocked_project_build')) {
        Add-Failure "Non-project Tcl is marked as a run.ps1 entry: $RelativePath"
    }
    if ($IsRunEntry -and $RelativePath -notmatch '/scripts/build\.tcl$') {
        Add-Failure "run.ps1 entry is not a project scripts/build.tcl: $RelativePath"
    }

    if ($Role -eq 'canonical_project_build') {
        $ApprovedDevice = [string]$Inventory.approved_target.device
        if ($Facts.Devices.Count -ne 1 -or $Facts.Devices[0] -ne $ApprovedDevice) {
            Add-Failure "Canonical project build does not uniquely target ${ApprovedDevice}: $RelativePath"
        }
        if ($Facts.ContainsAbsolutePaths) {
            Add-Failure "Canonical project build contains an absolute path: $RelativePath"
        }
    }

    if ($Role -eq 'migration_blocked_project_build') {
        if ($Facts.Devices -notcontains 'PG2L100H') {
            Add-Failure "Migration-blocked build no longer records PG2L100H; review its role: $RelativePath"
        }
        if ($Facts.ContainsAbsolutePaths) {
            Add-Failure "Migration-blocked project build contains an absolute path: $RelativePath"
        }
    }

    if ($Role -eq 'canonical_support_tool' -and
        $RelativePath -eq 'scripts/compile_simlib.tcl') {
        $SupportText = Get-Content -Raw -Encoding UTF8 -LiteralPath $FullPath
        if ($SupportText -notmatch 'PDS_SIMULATOR_EXEC_PATH') {
            Add-Failure 'compile_simlib.tcl lost its simulator-path environment override'
        }
    }

    Write-Host ("INFO: classified Tcl {0} as {1}" -f $RelativePath, $Role)
}

$RunEntries = @($Entries | Where-Object { [bool]$_.run_ps1_entry })
if ($RunEntries.Count -ne 2) {
    Add-Failure "Expected exactly two project run.ps1 Tcl entries, found $($RunEntries.Count)"
}

if ($Failures.Count -gt 0) {
    Write-Error ("PDS Tcl entrypoint gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host ("INFO: PDS Tcl entrypoint gate passed for {0} tracked files" -f `
        $TrackedTcl.Count)
exit 0
