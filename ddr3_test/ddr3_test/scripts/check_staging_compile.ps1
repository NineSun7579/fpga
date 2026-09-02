param(
    [string]$StagingRoot = '',

    [string]$RunRoot = '',

    [switch]$StaticOnly,

    [switch]$SelfTest
)

# Guard the M2-B2 compile-only boundary and optionally validate one dynamic
# run. This gate never promotes staging files into the canonical IP tree.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildScript = Join-Path $PSScriptRoot 'build_staging_compile.tcl'
$RunScript = Join-Path $PSScriptRoot 'run_staging_compile.ps1'
$DocPath = Join-Path $ProjectRoot 'doc\M2B2_STAGING_COMPILE.md'
$Failures = [System.Collections.Generic.List[string]]::new()

$ExpectedSources = @(
    'example_design/rtl/prbs15_64bit_v1_0.v',
    'example_design/rtl/prbs31_128bit_v1_0.v',
    'example_design/rtl/axi_bist_top_v1_0.v',
    'example_design/rtl/test_main_ctrl_v1_0.v',
    'example_design/rtl/test_rd_ctrl_v1_0.v',
    'example_design/rtl/test_wr_ctrl_v1_0.v',
    'example_design/rtl/uart_rd_lock.v',
    'example_design/rtl/test_ddr.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_clk_gen_32bit.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_cmd_parser_32bit.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_seu_rs232_intf.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_seu_uart_rx.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_seu_uart_tx.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_uart_ctrl_32bit.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_uart_ctrl_top_32bit.v',
    'example_design/rtl/uart_ctrl_32bit/ips2l_ver_ctrl_32bit.v',
    'example_design/rtl/adc/adc.v',
    'example_design/rtl/adc/adc_ctrl.v'
)

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
    return $true
}

function Get-TclContractFailures {
    param([Parameter(Mandatory)][string]$Text)

    $ContractFailures = [System.Collections.Generic.List[string]]::new()
    $RequiredPatterns = [ordered]@{
        'staging environment input' = 'DDR3_STAGING_ROOT'
        'run identifier input' = 'M2B2_RUN_ID'
        'PG2L50H target' = '-device\s+PG2L50H'
        'FBG484 package' = '-package\s+FBG484'
        'speed grade -6' = '-speedgrade\s+-6'
        'test_ddr compile top' = 'compile\s+-top_module\s+test_ddr'
        'staging IDF' = '\$staging_root/ddr3\.idf'
        '18-source marker' = 'M2B2_SOURCE_COUNT='
        'compile success marker' = 'M2B2_COMPILE_OK'
    }
    foreach ($Required in $RequiredPatterns.GetEnumerator()) {
        if ($Text -notmatch $Required.Value) {
            $ContractFailures.Add("missing $($Required.Key)")
        }
    }

    foreach ($Source in $ExpectedSources) {
        $Count = [regex]::Matches($Text, [regex]::Escape($Source)).Count
        if ($Count -ne 1) {
            $ContractFailures.Add("expected source '$Source' exactly once, found $Count")
        }
    }

    foreach ($Forbidden in @(
            'add_constraint',
            '\bsynthesize\b',
            '\bdev_map\b',
            '(?m)^\s*pnr\b',
            'ip_core[/\\]ddr3',
            'ip_backup'
        )) {
        if ($Text -match $Forbidden) {
            $ContractFailures.Add("forbidden Tcl pattern '$Forbidden'")
        }
    }

    return $ContractFailures
}

$BuildExists = Require-File -Path $BuildScript `
    -Description 'M2-B2 staging compile Tcl'
$RunExists = Require-File -Path $RunScript `
    -Description 'M2-B2 staging compile runner'
$DocExists = Require-File -Path $DocPath `
    -Description 'M2-B2 staging compile contract'

if ($BuildExists) {
    $BuildText = Get-Content -Raw -Encoding UTF8 -LiteralPath $BuildScript
    foreach ($Failure in @(Get-TclContractFailures -Text $BuildText)) {
        Add-Failure "Tcl contract: $Failure"
    }
}

if ($RunExists) {
    $RunText = Get-Content -Raw -Encoding UTF8 -LiteralPath $RunScript
    foreach ($Required in ([ordered]@{
            'fresh staging regeneration' = 'regenerate_ip\.ps1'
            'unique run directory' = 'run directory already exists'
            'process-local TEMP' = '\$env:TEMP\s*='
            'process-local TMP' = '\$env:TMP\s*='
            'canonical SHA-256 gate' = 'Get-CanonicalHashes'
            'dynamic summary' = 'summary\.json'
            'dynamic gate invocation' = 'check_staging_compile\.ps1'
        }).GetEnumerator()) {
        if ($RunText -notmatch $Required.Value) {
            Add-Failure "Runner contract missing $($Required.Key)"
        }
    }
}

if ($DocExists) {
    $DocText = Get-Content -Raw -Encoding UTF8 -LiteralPath $DocPath
    foreach ($Required in ([ordered]@{
            'PG2L50H target' = 'Logos2 / PG2L50H / FBG484 / -6'
            '18 example sources' = '18\s+\u4e2a.*RTL'
            '26 top ports' = '26\s+\u4e2a\u7aef\u53e3'
            'constraint exclusion' = 'FDC/RCF'
            'implementation exclusion' = 'synthesize.*dev_map.*PNR'
            'canonical promotion exclusion' = 'canonical'
            'board limitation' = 'VCCIO.*VREF.*ODT'
        }).GetEnumerator()) {
        if ($DocText -notmatch $Required.Value) {
            Add-Failure "Documentation contract missing $($Required.Key)"
        }
    }
}

if ($SelfTest -and $BuildExists) {
    $WrongDeviceText = $BuildText -replace 'PG2L50H', 'PG2L100H'
    if (@(Get-TclContractFailures -Text $WrongDeviceText).Count -eq 0) {
        Add-Failure 'Self-test failed to reject a PG2L100H Tcl target'
    }

    $WrongSourceText = $BuildText.Replace(
        $ExpectedSources[0],
        'ip_core/ddr3/example_design/rtl/prbs15_64bit_v1_0.v'
    )
    if (@(Get-TclContractFailures -Text $WrongSourceText).Count -eq 0) {
        Add-Failure 'Self-test failed to reject a canonical source path'
    }
}

if (-not $StaticOnly -and -not [string]::IsNullOrWhiteSpace($RunRoot)) {
    if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
        $StagingRoot = Join-Path $ProjectRoot 'build\ipgen\pg2l50h'
    } elseif (-not [IO.Path]::IsPathRooted($StagingRoot)) {
        $StagingRoot = Join-Path $ProjectRoot $StagingRoot
    }
    $StagingRoot = [IO.Path]::GetFullPath($StagingRoot)
    $RunRoot = [IO.Path]::GetFullPath($RunRoot)
    $SummaryPath = Join-Path $RunRoot 'summary.json'
    $PdsLog = Join-Path $RunRoot 'logs\pds-compile.log'
    $CmrPath = Join-Path $RunRoot 'pds\compile\test_ddr.cmr'
    $ImplTclPath = Join-Path $RunRoot 'pds\impl.tcl'

    if (Require-File -Path $SummaryPath -Description 'M2-B2 run summary') {
        try {
            $Summary = Get-Content -Raw -Encoding UTF8 -LiteralPath $SummaryPath |
                ConvertFrom-Json
        } catch {
            Add-Failure "M2-B2 summary is not valid JSON: $($_.Exception.Message)"
        }
    }

    if ($null -ne $Summary) {
        if ($Summary.status -cne 'complete') {
            Add-Failure "M2-B2 summary status is '$($Summary.status)'"
        }
        if ($Summary.target -cne 'Logos2 / PG2L50H / FBG484 / -6') {
            Add-Failure "M2-B2 summary target is '$($Summary.target)'"
        }
        if ($Summary.top_module -cne 'test_ddr' -or
            [int]$Summary.source_count -ne 18 -or
            [int]$Summary.port_count -ne 26) {
            Add-Failure 'M2-B2 summary top/source/port contract mismatch'
        }
        if ([int]$Summary.pds_exit_code -ne 0 -or
            [int]$Summary.error_records -ne 0) {
            Add-Failure 'M2-B2 summary records a failed PDS compile'
        }

        $BeforeProperties = @($Summary.canonical_hashes_before.psobject.Properties)
        $AfterProperties = @($Summary.canonical_hashes_after.psobject.Properties)
        if ($BeforeProperties.Count -ne 4 -or $AfterProperties.Count -ne 4) {
            Add-Failure 'M2-B2 summary does not contain four canonical hashes'
        } else {
            foreach ($Property in $BeforeProperties) {
                $AfterValue = $Summary.canonical_hashes_after.($Property.Name)
                if ([string]$Property.Value -cne [string]$AfterValue) {
                    Add-Failure "Canonical hash changed: $($Property.Name)"
                }
            }
        }
    }

    if (Require-File -Path $PdsLog -Description 'M2-B2 PDS log') {
        $LogText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PdsLog
        if ($LogText -match '(?m)^E:') {
            Add-Failure 'M2-B2 PDS log contains an error record'
        }
        if ($LogText -match '(?i)^License checkout:') {
            Add-Failure 'M2-B2 PDS log contains unredacted license checkout details'
        }
        if ($null -ne $Summary) {
            $PassPattern = 'INFO: M2B2_COMPILE_OK run_id=' +
                [regex]::Escape([string]$Summary.run_id)
            if ([regex]::Matches($LogText, $PassPattern).Count -ne 1) {
                Add-Failure 'M2-B2 PDS log does not contain one matching PASS marker'
            }
        }
    }

    if (Require-File -Path $ImplTclPath -Description 'M2-B2 generated impl.tcl') {
        $ImplTclText = Get-Content -Raw -Encoding UTF8 -LiteralPath $ImplTclPath
        foreach ($RequiredPattern in @(
                '-device\s+PG2L50H',
                '-package\s+FBG484',
                '-speedgrade\s+-6',
                'compile\s+-top_module\s+\{?test_ddr\}?'
            )) {
            if ($ImplTclText -notmatch $RequiredPattern) {
                Add-Failure "M2-B2 impl.tcl missing '$RequiredPattern'"
            }
        }
        foreach ($ForbiddenPattern in @(
                '\bsynthesize\b',
                '\bdev_map\b',
                '(?m)^\s*pnr\b',
                'add_constraint'
            )) {
            if ($ImplTclText -match $ForbiddenPattern) {
                Add-Failure "M2-B2 impl.tcl contains '$ForbiddenPattern'"
            }
        }
    }

    if (Require-File -Path $CmrPath -Description 'M2-B2 compile manifest') {
        $CmrText = Get-Content -Raw -Encoding UTF8 -LiteralPath $CmrPath
        $InputSection = [regex]::Match(
            $CmrText,
            '(?s)\|\s*Input\s*\|(?<inputs>.*?)\|\s*Output\s*\|'
        )
        if (-not $InputSection.Success) {
            Add-Failure 'M2-B2 compile manifest input table was not parsed'
        } else {
            $InputPaths = @(
                [regex]::Matches(
                    $InputSection.Groups['inputs'].Value,
                    '(?im)([A-Z]:[/\\][^\r\n|]+?\.(?:v|idf))\s*(?:\||$)'
                ) | ForEach-Object {
                    $_.Groups[1].Value.Trim().Replace('\', '/')
                }
            )
            $ExpectedInputPaths = @(
                $ExpectedSources | ForEach-Object {
                    (Join-Path $StagingRoot $_).Replace('\', '/')
                }
            ) + (Join-Path $StagingRoot 'ddr3.idf').Replace('\', '/')

            $InputDiff = @(Compare-Object -CaseSensitive `
                -ReferenceObject ($ExpectedInputPaths | Sort-Object) `
                -DifferenceObject ($InputPaths | Sort-Object))
            if ($InputPaths.Count -ne 19 -or $InputDiff.Count -ne 0) {
                Add-Failure 'M2-B2 compile manifest does not contain exactly the 19 staging inputs'
            }
            if ($InputSection.Value -match 'ip_core[/\\]ddr3|ip_backup') {
                Add-Failure 'M2-B2 compile manifest contains canonical or backup inputs'
            }
        }
    }

    foreach ($Artifact in @(
            'pds\compile\test_ddr_comp.adf',
            'pds\compile\test_ddr.cmr',
            'pds\compile\cmr.db'
        )) {
        $ArtifactPath = Join-Path $RunRoot $Artifact
        if (Require-File -Path $ArtifactPath -Description "M2-B2 artifact $Artifact") {
            if ((Get-Item -LiteralPath $ArtifactPath).Length -le 0) {
                Add-Failure "M2-B2 artifact is empty: $Artifact"
            }
        }
    }

    $ForbiddenArtifacts = @(Get-ChildItem -LiteralPath $RunRoot -File -Recurse |
        Where-Object {
            $_.Name -match '(?:_syn\.vm|\.sdf|\.sbit|\.bin)$'
        })
    if ($ForbiddenArtifacts.Count -gt 0) {
        Add-Failure 'M2-B2 run unexpectedly produced post-compile artifacts'
    }
}

if ($Failures.Count -gt 0) {
    throw "M2-B2 staging compile gate failed:`n - $($Failures -join "`n - ")"
}

if ($SelfTest) {
    Write-Host 'INFO: M2-B2 negative self-tests passed'
}
if (-not [string]::IsNullOrWhiteSpace($RunRoot)) {
    Write-Host 'INFO: M2-B2 dynamic compile evidence passed'
} else {
    Write-Host 'INFO: M2-B2 static compile contract passed'
}
