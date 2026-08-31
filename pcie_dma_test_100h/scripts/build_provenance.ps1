# Shared PCIe PDS provenance helpers. All manifest paths are project-relative
# POSIX paths, while hashes are calculated from the original file bytes.

function Get-PdsProvenanceManifestPath {
    param([Parameter(Mandatory)][string]$ProjectRoot)

    return Join-Path $ProjectRoot 'build\provenance\pds-build.json'
}

function ConvertTo-PdsRelativePath {
    param([Parameter(Mandatory)][string]$Path)

    $RelativePath = $Path.Replace('\', '/')
    if ([IO.Path]::IsPathRooted($RelativePath) -or
        $RelativePath -match '(^|/)\.\.(/|$)') {
        throw "Invalid project-relative path: $Path"
    }
    return $RelativePath
}

function Resolve-PdsProjectFile {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RelativePath
    )

    $NormalizedRelativePath = (ConvertTo-PdsRelativePath -Path $RelativePath).
        Replace('/', [IO.Path]::DirectorySeparatorChar)
    $ResolvedRoot = [IO.Path]::GetFullPath($ProjectRoot)
    $ResolvedPath = [IO.Path]::GetFullPath(
        (Join-Path $ResolvedRoot $NormalizedRelativePath)
    )
    $RootPrefix = $ResolvedRoot.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar

    if (-not $ResolvedPath.StartsWith(
        $RootPrefix,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Path escapes project root: $RelativePath"
    }
    return $ResolvedPath
}

function Get-PdsSourcePaths {
    param([Parameter(Mandatory)][string]$ProjectRoot)

    $SourceListPath = Resolve-PdsProjectFile `
        -ProjectRoot $ProjectRoot `
        -RelativePath 'scripts/pds_sources.f'
    if (-not (Test-Path -LiteralPath $SourceListPath -PathType Leaf)) {
        throw "PDS source list not found: $SourceListPath"
    }

    $SourcePaths = [Collections.Generic.List[string]]::new()
    foreach ($Line in Get-Content -LiteralPath $SourceListPath) {
        $RelativePath = $Line.Trim()
        if ([string]::IsNullOrWhiteSpace($RelativePath) -or
            $RelativePath.StartsWith('#')) {
            continue
        }
        $SourcePaths.Add((ConvertTo-PdsRelativePath -Path $RelativePath))
    }

    if ($SourcePaths.Count -eq 0) {
        throw "PDS source list is empty: $SourceListPath"
    }
    $Duplicates = @($SourcePaths | Group-Object -CaseSensitive |
        Where-Object Count -gt 1)
    if ($Duplicates.Count -gt 0) {
        throw "PDS source list contains duplicate paths: $($Duplicates.Name -join ', ')"
    }
    return @($SourcePaths)
}

function Get-PdsCanonicalInputPaths {
    param([Parameter(Mandatory)][string]$ProjectRoot)

    $Paths = [Collections.Generic.List[string]]::new()
    foreach ($Path in @(
            'scripts/run.ps1',
            'scripts/build.tcl',
            'scripts/build_provenance.ps1',
            'scripts/pds_sources.f'
        )) {
        $Paths.Add($Path)
    }
    foreach ($Path in Get-PdsSourcePaths -ProjectRoot $ProjectRoot) {
        $Paths.Add($Path)
    }
    $Paths.Add('ipcore/pcie_test/pcie_test.idf')
    $Paths.Add('fdc/pcie_dma_test.fdc')

    return @($Paths)
}

function Get-PdsArtifactPaths {
    return @(
        'build/logs/pds-gen_bit_stream.log',
        'build/pds/report_timing/pcie_dma_test.rtr',
        'build/pds/generate_netlist/pcie_dma_test_sim.v',
        'build/pds/generate_netlist/pcie_dma_test_sta.sdf',
        'build/pds/generate_bitstream/pcie_dma_test.sbit',
        'build/pds/generate_bitstream/pcie_dma_test.bin',
        'build/pds/generate_bitstream/bgr.db'
    )
}

function Get-PdsFileRecord {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RelativePath
    )

    $CanonicalPath = ConvertTo-PdsRelativePath -Path $RelativePath
    $FullPath = Resolve-PdsProjectFile `
        -ProjectRoot $ProjectRoot `
        -RelativePath $CanonicalPath
    if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
        throw "Provenance file not found: $CanonicalPath"
    }

    $File = Get-Item -LiteralPath $FullPath
    if ($File.Length -le 0) {
        throw "Provenance file is empty: $CanonicalPath"
    }

    return [ordered]@{
        path = $CanonicalPath
        length = [long]$File.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $FullPath).Hash
    }
}

function Get-PdsFileRecords {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string[]]$RelativePaths
    )

    return @($RelativePaths | ForEach-Object {
            Get-PdsFileRecord -ProjectRoot $ProjectRoot -RelativePath $_
        })
}

function Assert-PdsFileRecordsMatch {
    param(
        [Parameter(Mandatory)][object[]]$Expected,
        [Parameter(Mandatory)][object[]]$Actual,
        [Parameter(Mandatory)][string]$Description
    )

    $ExpectedByPath = [Collections.Generic.Dictionary[string, object]]::new(
        [StringComparer]::Ordinal
    )
    $ActualByPath = [Collections.Generic.Dictionary[string, object]]::new(
        [StringComparer]::Ordinal
    )
    foreach ($Entry in $Expected) {
        $Path = [string]$Entry.path
        if ([string]::IsNullOrWhiteSpace($Path) -or
            $ExpectedByPath.ContainsKey($Path)) {
            throw "$Description expected records contain an empty or duplicate path: $Path"
        }
        $ExpectedByPath.Add($Path, $Entry)
    }
    foreach ($Entry in $Actual) {
        $Path = [string]$Entry.path
        if ([string]::IsNullOrWhiteSpace($Path) -or
            $ActualByPath.ContainsKey($Path)) {
            throw "$Description actual records contain an empty or duplicate path: $Path"
        }
        $ActualByPath.Add($Path, $Entry)
    }

    $Differences = [Collections.Generic.List[string]]::new()
    $AllPaths = @($ExpectedByPath.Keys) + @($ActualByPath.Keys) |
        Sort-Object -CaseSensitive -Unique
    foreach ($Path in $AllPaths) {
        if (-not $ExpectedByPath.ContainsKey($Path)) {
            $Differences.Add("unexpected path $Path")
            continue
        }
        if (-not $ActualByPath.ContainsKey($Path)) {
            $Differences.Add("missing path $Path")
            continue
        }

        $ExpectedRecord = $ExpectedByPath[$Path]
        $ActualRecord = $ActualByPath[$Path]
        if ([long]$ExpectedRecord.length -ne [long]$ActualRecord.length) {
            $Differences.Add("$Path length expected=$($ExpectedRecord.length) actual=$($ActualRecord.length)")
        }
        if ([string]$ExpectedRecord.sha256 -cne [string]$ActualRecord.sha256) {
            $Differences.Add("$Path SHA-256 changed")
        }
    }

    if ($Differences.Count -gt 0) {
        throw ("{0} changed:`n- {1}" -f $Description, ($Differences -join "`n- "))
    }
}

function Write-PdsProvenanceManifest {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][object]$Manifest,
        [Parameter(Mandatory)][string]$RunId
    )

    $Directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    $TemporaryPath = "$Path.$RunId.tmp"
    $BackupPath = "$Path.$RunId.bak"
    $Utf8NoBom = New-Object Text.UTF8Encoding($false)
    $Json = $Manifest | ConvertTo-Json -Depth 8

    try {
        [IO.File]::WriteAllText($TemporaryPath, $Json + "`n", $Utf8NoBom)
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            [IO.File]::Replace($TemporaryPath, $Path, $BackupPath, $false)
            if (Test-Path -LiteralPath $BackupPath -PathType Leaf) {
                Remove-Item -LiteralPath $BackupPath -Force
            }
        } else {
            [IO.File]::Move($TemporaryPath, $Path)
        }
    } finally {
        if (Test-Path -LiteralPath $TemporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $TemporaryPath -Force
        }
        if (Test-Path -LiteralPath $BackupPath -PathType Leaf) {
            Remove-Item -LiteralPath $BackupPath -Force
        }
    }
}
