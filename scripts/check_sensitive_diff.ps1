param(
    [string]$RepoRoot,
    [string]$BaseRef = 'origin/main',
    [switch]$SelfTest,
    [switch]$FullTree
)

# Reject vendor-license configuration without reading or printing local
# license environment values. Diff mode checks additions; FullTree checks the
# current tracked and untracked worktree after legacy logs have been redacted.
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$AbsolutePathPrefixPattern = '(?i)(?:\b[A-Z]:' + '[\\/]|\\\\|' +
    '(?<![A-Za-z0-9._:/-])/(?:[^/\s]+/)+)'
$LicenseNamePattern = '(?:' + 'licen' + '[cs]e|' + '\.' + 'lic\b)'
$AbsoluteLicensePathPattern = $AbsolutePathPrefixPattern + '[^\r\n]*' +
    $LicenseNamePattern

function Test-PlaceholderValue {
    param([Parameter(Mandatory)][string]$Value)

    $Normalized = $Value.Trim().Trim("'", '"')
    return $Normalized -in @(
        '<license-source>',
        '<license-file>',
        '<license-path>',
        '<port>@<host>'
    ) -or
        $Normalized -match '^\$\{[^}]+\}$' -or
        $Normalized -match '^\$env:[A-Za-z_][A-Za-z0-9_]*$' -or
        $Normalized -match '^%[A-Za-z_][A-Za-z0-9_]*%$' -or
        $Normalized -match '^\$::env\([A-Za-z_][A-Za-z0-9_]*\)$'
}

function Test-ForbiddenLicensePath {
    param([Parameter(Mandatory)][string]$Path)

    $Normalized = $Path -replace '\\', '/'
    $SeparatorPattern = [string][char]47
    $LicenseDataNamePattern = 'licen' + '[cs]e\.dat'
    $LicenseExtensionPattern = '(?:' + 'lic|' + 'license|' + 'flexlm)'
    $FileNamePattern = '(?:\.flexlmrc|flexlmrc|' + $LicenseDataNamePattern +
        '|[^' + $SeparatorPattern + ']+\.' + $LicenseExtensionPattern +
        '(?:\.(?:bak|old))?)'
    return $Normalized -match ('(?i)(?:^|' + $SeparatorPattern + ')' +
        $FileNamePattern + '$')
}

function Get-TextLines {
    param([Parameter(Mandatory)][string]$Path)

    $Stream = [System.IO.File]::OpenRead($Path)
    try {
        $PrefixLength = [Math]::Min(4096, [int]$Stream.Length)
        $Prefix = New-Object byte[] $PrefixLength
        $ReadCount = $Stream.Read($Prefix, 0, $PrefixLength)
        if ($ReadCount -eq 0) {
            return
        }
        $HasTextBom = $ReadCount -ge 2 -and (
            ($Prefix[0] -eq 0xFF -and $Prefix[1] -eq 0xFE) -or
            ($Prefix[0] -eq 0xFE -and $Prefix[1] -eq 0xFF) -or
            ($ReadCount -ge 3 -and $Prefix[0] -eq 0xEF -and
                $Prefix[1] -eq 0xBB -and $Prefix[2] -eq 0xBF))
        if (-not $HasTextBom -and $Prefix[0..([Math]::Max(0, $ReadCount - 1))] -contains 0) {
            return
        }
        $Stream.Position = 0
        $Reader = [System.IO.StreamReader]::new(
            $Stream,
            [System.Text.Encoding]::UTF8,
            $true,
            4096,
            $true)
        try {
            while (($Line = $Reader.ReadLine()) -ne $null) {
                Write-Output $Line
            }
        } finally {
            $Reader.Dispose()
        }
    } finally {
        $Stream.Dispose()
    }
}

function Get-AddedLineViolation {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Line)

    if ($Line -match $AbsoluteLicensePathPattern) {
        return 'absolute license path'
    }

    $EnvironmentAssignment = [regex]::Match(
        $Line,
        '(?i)\b(?:LM_LICENSE_FILE|MGLS_LICENSE_FILE|PANGO_LICENSE_FILE|SNPSLMD_LICENSE_FILE|SALT_LICENSE_SERVER|[A-Z][A-Z0-9_]*_LICENSE_FILE)\b\s*(?:=|:)\s*(?<value>.+)$')
    if ($EnvironmentAssignment.Success -and
        -not (Test-PlaceholderValue -Value $EnvironmentAssignment.Groups['value'].Value)) {
        return 'license environment variable contains an actual value'
    }

    if ($Line -match '(?i)\b\d{2,5}@[A-Za-z0-9][A-Za-z0-9.-]*\b') {
        return 'license server endpoint'
    }

    if ($Line -match '(?i)^\s*USE_SERVER\s*$' -or
        $Line -match '(?i)^\s*(?:SERVER|VENDOR|DAEMON)\s+\S+\s+\S+' -or
        $Line -match '(?i)^\s*(?:FEATURE|INCREMENT|UPGRADE|PACKAGE)\s+(?:\S+\s+){4,}\S+') {
        return 'FlexNet license content'
    }

    if ($Line -match '(?i)\b(?:SIGN|SIGN2|VENDOR_STRING|HOSTID|FLEXID)\s*=\s*[A-Za-z0-9+/=_-]{8,}') {
        return 'license signature or host identifier'
    }

    return $null
}

function Invoke-SelfTest {
    # Build forbidden examples from fragments so this gate does not need to
    # exempt its own source from the same added-line rules.
    $EnvironmentName = 'MGLS' + '_LICENSE_FILE'
    $PangoEnvironmentName = 'PANGO' + '_LICENSE_FILE'
    $ForbiddenEnvironment = $EnvironmentName + '=' + 'X:' + '/private/' +
        'license' + '.lic'
    $ForbiddenServer = 'License server: ' + '27000' + '@' + 'private-host'
    $ForbiddenFeature = 'FEATURE ' + 'private_feature vendor 1.0 permanent 1 ' +
        'SIGN=' + 'ABCDEF123456'
    $ForbiddenUnixPath = '/opt/' + 'vendor/' +
        'license' + '.lic'
    $AllowedRelativeLink = '[gate](../docs/' + 'SENSITIVE_DIFF_GATE.md): ' +
        'license policy'

    $LineCases = @(
        [pscustomobject]@{
            Name = 'placeholder environment value'
            Line = $EnvironmentName + '=<license-source>'
            MustFail = $false
        },
        [pscustomobject]@{
            Name = 'placeholder server value'
            Line = '<port>@<host>'
            MustFail = $false
        },
        [pscustomobject]@{
            Name = 'relative Markdown link near license prose'
            Line = $AllowedRelativeLink
            MustFail = $false
        },
        [pscustomobject]@{
            Name = 'arbitrary angle-bracket value'
            Line = $EnvironmentName + '=<actual-looking-value>'
            MustFail = $true
        },
        [pscustomobject]@{
            Name = 'actual environment value'
            Line = $ForbiddenEnvironment
            MustFail = $true
        },
        [pscustomobject]@{
            Name = 'Pango environment value'
            Line = $PangoEnvironmentName + '=' + 'private-source'
            MustFail = $true
        },
        [pscustomobject]@{
            Name = 'actual server endpoint'
            Line = $ForbiddenServer
            MustFail = $true
        },
        [pscustomobject]@{
            Name = 'license feature content'
            Line = $ForbiddenFeature
            MustFail = $true
        },
        [pscustomobject]@{
            Name = 'actual Unix license path'
            Line = $ForbiddenUnixPath
            MustFail = $true
        }
    )

    foreach ($Case in $LineCases) {
        $Violation = Get-AddedLineViolation -Line $Case.Line
        $Failed = -not [string]::IsNullOrWhiteSpace($Violation)
        if ($Failed -ne $Case.MustFail) {
            throw "Sensitive diff self-test failed: $($Case.Name)"
        }
    }

    $ForbiddenFile = 'secrets/' + 'tool' + '.lic'
    if (-not (Test-ForbiddenLicensePath -Path $ForbiddenFile)) {
        throw 'Sensitive diff self-test failed: license file path was accepted'
    }
    if (Test-ForbiddenLicensePath -Path 'docs/LICENSE.md') {
        throw 'Sensitive diff self-test failed: open-source LICENSE.md was rejected'
    }

    Write-Host 'INFO: sensitive diff gate self-test passed'
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

if ($FullTree) {
    $TrackedPaths = @(& git -C $RepoRoot ls-files)
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'git ls-files failed while enumerating tracked paths'
        exit 1
    }
    $UntrackedPaths = @(& git -C $RepoRoot ls-files --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'git ls-files failed while enumerating untracked paths'
        exit 1
    }

    $Failures = [System.Collections.Generic.List[string]]::new()
    $FailureKeys = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase)
    $ScannedLineCount = 0
    $AllPaths = @($TrackedPaths + $UntrackedPaths | Sort-Object -Unique)

    foreach ($Path in $AllPaths) {
        if (Test-ForbiddenLicensePath -Path $Path) {
            $Key = "$Path|license file path"
            if ($FailureKeys.Add($Key)) {
                $Failures.Add("${Path}: license file path")
            }
        }
    }

    # Let Git prefilter tracked text lines. Reading every vendor database and
    # multi-megabyte PDS log through PowerShell makes the full-tree gate slow.
    $CandidatePattern = 'licen[cs]e|\.lic([^A-Za-z0-9]|$)|' +
        '_LICENSE_FILE|SALT_LICENSE_SERVER|[0-9]{2,5}@[A-Za-z0-9]|' +
        '^[[:space:]]*(USE_SERVER|SERVER|VENDOR|DAEMON|FEATURE|INCREMENT|' +
        'UPGRADE|PACKAGE)[[:space:]]+|' +
        '(SIGN|SIGN2|VENDOR_STRING|HOSTID|FLEXID)[[:space:]]*=' +
        '[[:space:]]*[A-Za-z0-9+/=_-]{8,}'
    $TrackedCandidateLines = @(& git -C $RepoRoot grep -n -I -i -E `
            $CandidatePattern -- . ':(exclude)*.log')
    $TextGrepExitCode = $LASTEXITCODE
    $TrackedLogCandidateLines = @(& git -C $RepoRoot grep -n -a -i -E `
            $CandidatePattern -- '*.log')
    $LogGrepExitCode = $LASTEXITCODE
    if ($TextGrepExitCode -notin @(0, 1) -or $LogGrepExitCode -notin @(0, 1)) {
        Write-Error 'git grep failed while prefiltering tracked text lines'
        exit 1
    }
    foreach ($Candidate in @($TrackedCandidateLines + $TrackedLogCandidateLines)) {
        $Match = [regex]::Match(
            $Candidate,
            '^(?<path>.*?):(?<line>\d+):(?<text>.*)$')
        if (-not $Match.Success) {
            continue
        }
        $ScannedLineCount++
        $Path = $Match.Groups['path'].Value
        $Violation = Get-AddedLineViolation -Line $Match.Groups['text'].Value
        if ([string]::IsNullOrWhiteSpace($Violation)) {
            continue
        }
        $Key = "$Path|$Violation"
        if ($FailureKeys.Add($Key)) {
            $Failures.Add("${Path}: $Violation")
        }
    }

    foreach ($Path in $UntrackedPaths) {
        $FullPath = Join-Path $RepoRoot ($Path -replace '/', '\\')
        if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
            continue
        }
        foreach ($Line in @(Get-TextLines -Path $FullPath)) {
            $ScannedLineCount++
            $Violation = Get-AddedLineViolation -Line $Line
            if ([string]::IsNullOrWhiteSpace($Violation)) {
                continue
            }
            $Key = "$Path|$Violation"
            if ($FailureKeys.Add($Key)) {
                $Failures.Add("${Path}: $Violation")
            }
        }
    }

    if ($Failures.Count -gt 0) {
        Write-Error ("Sensitive full-tree gate failed with {0} issue(s):`n- {1}" -f `
                $Failures.Count, ($Failures -join "`n- "))
        exit 1
    }

    Write-Host ("INFO: sensitive full-tree gate passed; checked {0} path(s) and {1} text line(s)" -f `
            $AllPaths.Count, $ScannedLineCount)
    exit 0
}

if ([string]::IsNullOrWhiteSpace($BaseRef)) {
    Write-Error 'Sensitive diff base ref must not be empty'
    exit 1
}

& git -C $RepoRoot rev-parse --verify --quiet "$BaseRef^{commit}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Sensitive diff base ref does not resolve to a commit: $BaseRef"
    exit 1
}

$MergeBase = @(& git -C $RepoRoot merge-base $BaseRef HEAD)
if ($LASTEXITCODE -ne 0 -or $MergeBase.Count -ne 1) {
    Write-Error "Unable to resolve a unique merge base for: $BaseRef"
    exit 1
}
$DiffBase = $MergeBase[0].Trim()

$ChangedPaths = @(& git -C $RepoRoot diff --name-only `
        --diff-filter=ACMRTUXB $DiffBase --)
if ($LASTEXITCODE -ne 0) {
    Write-Error 'git diff failed while enumerating changed paths'
    exit 1
}
$UntrackedPaths = @(& git -C $RepoRoot ls-files --others --exclude-standard)
if ($LASTEXITCODE -ne 0) {
    Write-Error 'git ls-files failed while enumerating untracked paths'
    exit 1
}

$Failures = [System.Collections.Generic.List[string]]::new()
$FailureKeys = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase)

foreach ($Path in @($ChangedPaths + $UntrackedPaths | Sort-Object -Unique)) {
    if (Test-ForbiddenLicensePath -Path $Path) {
        $Key = "$Path|license file path"
        if ($FailureKeys.Add($Key)) {
            $Failures.Add("${Path}: license file path")
        }
    }
}

$DiffLines = @(& git -C $RepoRoot -c core.quotePath=false diff `
        --unified=0 --no-color --no-ext-diff $DiffBase --)
if ($LASTEXITCODE -ne 0) {
    Write-Error 'git diff failed while reading added lines'
    exit 1
}

$AddedLineCount = 0
foreach ($UntrackedPath in $UntrackedPaths) {
    $FullPath = Join-Path $RepoRoot ($UntrackedPath -replace '/', '\\')
    if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
        continue
    }
    foreach ($Line in @(Get-TextLines -Path $FullPath)) {
        $AddedLineCount++
        $Violation = Get-AddedLineViolation -Line $Line
        if ([string]::IsNullOrWhiteSpace($Violation)) {
            continue
        }
        $Key = "$UntrackedPath|$Violation"
        if ($FailureKeys.Add($Key)) {
            $Failures.Add("${UntrackedPath}: $Violation")
        }
    }
}

$CurrentPath = '<unknown>'
foreach ($DiffLine in $DiffLines) {
    if ($DiffLine -match '^\+\+\+ b/(.+)$') {
        $CurrentPath = $Matches[1]
        continue
    }
    if ($DiffLine -notmatch '^\+' -or $DiffLine -match '^\+\+\+') {
        continue
    }

    $AddedLineCount++
    $Violation = Get-AddedLineViolation -Line $DiffLine.Substring(1)
    if ([string]::IsNullOrWhiteSpace($Violation)) {
        continue
    }

    $Key = "$CurrentPath|$Violation"
    if ($FailureKeys.Add($Key)) {
        $Failures.Add("${CurrentPath}: $Violation")
    }
}

if ($Failures.Count -gt 0) {
    Write-Error ("Sensitive diff gate failed with {0} issue(s):`n- {1}" -f `
            $Failures.Count, ($Failures -join "`n- "))
    exit 1
}

Write-Host ("INFO: sensitive diff gate passed against merge-base of {0}; checked {1} path(s) and {2} added line(s)" -f `
        $BaseRef, @($ChangedPaths + $UntrackedPaths | Sort-Object -Unique).Count,
        $AddedLineCount)
exit 0
