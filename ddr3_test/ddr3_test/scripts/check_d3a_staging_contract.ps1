param(
    [string]$StagingRoot = '',

    [switch]$StaticOnly,

    [switch]$SelfTest
)

# Verify the D3-0-M boundary between the historical canonical DDR3 wrapper
# and freshly generated PG2L50H staging assets. This gate is read-only and
# never promotes generated files into ip_core/ddr3.
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CanonicalCorePath = Join-Path $ProjectRoot 'ip_core\ddr3\ddr3.v'
$CanonicalWrapperPath = Join-Path $ProjectRoot `
    'ip_core\ddr3\example_design\rtl\test_ddr.v'
$ReviewPath = Join-Path $ProjectRoot `
    'doc\D3A_PG2L50H_STAGING_REVIEW.md'
$PortMapPath = Join-Path $ProjectRoot 'doc\D3A_PORT_MAP.md'
$Failures = [System.Collections.Generic.List[string]]::new()

$ExpectedAddedWrapperPorts = @(
    'ddr_init_done',
    'ddrphy_cpd_lock',
    'pll_lock',
    'ref_clk_n',
    'ref_clk_p'
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

function Get-ModuleHeader {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$ModuleName
    )

    $Match = [regex]::Match(
        $Text,
        "(?ms)^module\s+$([regex]::Escape($ModuleName))\b.*?^\s*\);\s*$"
    )
    if (-not $Match.Success) {
        throw "Module header '$ModuleName' was not found"
    }
    return $Match.Value
}

function Get-NormalizedText {
    param(
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string]$Text
    )

    return (($Text -replace '(?s)/\*.*?\*/', '' `
            -replace '(?m)//[^\r\n]*$', '' `
            -replace '\s+', ' ').Trim())
}

function Get-ModulePorts {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$ModuleName
    )

    $Header = Get-ModuleHeader -Text $Text -ModuleName $ModuleName
    return @(
        [regex]::Matches(
            $Header,
            '(?m)^\s*(?:input|output|inout)\s+' +
                '(?:(?:wire|reg|logic)\s+)?' +
                '(?:\[[^\]]+\]\s+)?' +
                '(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:,|$)'
        ) | ForEach-Object { $_.Groups['name'].Value }
    )
}

function Get-DdrInstanceConnections {
    param([Parameter(Mandatory)][string]$Text)

    $Instance = [regex]::Match(
        $Text,
        '(?ms)\bddr3\s*#\s*\(.*?\)\s*I_ips_ddr_top\s*\(' +
            '(?<ports>.*?)^\s*\);\s*$'
    )
    if (-not $Instance.Success) {
        throw 'DDR3 instance I_ips_ddr_top was not found'
    }

    $Connections = [ordered]@{}
    foreach ($Connection in [regex]::Matches(
            $Instance.Groups['ports'].Value,
            '\.(?<port>[A-Za-z_][A-Za-z0-9_]*)\s*' +
                '\(\s*(?<signal>[^\)]*?)\s*\)')) {
        $Port = $Connection.Groups['port'].Value
        $Signal = Get-NormalizedText -Text $Connection.Groups['signal'].Value
        if ($Connections.Contains($Port)) {
            throw "Duplicate I_ips_ddr_top connection '$Port'"
        }
        $Connections[$Port] = $Signal
    }
    return $Connections
}

function Get-WrapperContractFailures {
    param(
        [Parameter(Mandatory)][string]$CanonicalCoreText,
        [Parameter(Mandatory)][string]$CanonicalWrapperText,
        [Parameter(Mandatory)][string]$StagingCoreText,
        [Parameter(Mandatory)][string]$StagingWrapperText
    )

    $ContractFailures = [System.Collections.Generic.List[string]]::new()
    $CanonicalCoreHeader = Get-NormalizedText -Text `
        (Get-ModuleHeader -Text $CanonicalCoreText -ModuleName 'ddr3')
    $StagingCoreHeader = Get-NormalizedText -Text `
        (Get-ModuleHeader -Text $StagingCoreText -ModuleName 'ddr3')
    if ($CanonicalCoreHeader -cne $StagingCoreHeader) {
        $ContractFailures.Add('PG2L50H core public module header changed')
    }

    foreach ($CoreText in @($CanonicalCoreText, $StagingCoreText)) {
        foreach ($Required in @(
                'axi_wready',
                'axi_wusero_last',
                'axi_rvalid',
                'axi_rlast',
                'ddr_init_done',
                'core_clk'
            )) {
            if ($CoreText -notmatch [regex]::Escape($Required)) {
                $ContractFailures.Add("DDR3 core is missing '$Required'")
            }
        }
        if ($CoreText -match '(?i)axi_rready') {
            $ContractFailures.Add('DDR3 core unexpectedly declares axi_rready')
        }
    }

    $CanonicalPorts = @(Get-ModulePorts -Text $CanonicalWrapperText `
        -ModuleName 'test_ddr' | Sort-Object -CaseSensitive)
    $StagingPorts = @(Get-ModulePorts -Text $StagingWrapperText `
        -ModuleName 'test_ddr' | Sort-Object -CaseSensitive)
    $AddedPorts = @(
        Compare-Object -CaseSensitive -ReferenceObject $CanonicalPorts `
            -DifferenceObject $StagingPorts |
            Where-Object SideIndicator -eq '=>' |
            ForEach-Object InputObject |
            Sort-Object -CaseSensitive
    )
    $RemovedPorts = @(
        Compare-Object -CaseSensitive -ReferenceObject $CanonicalPorts `
            -DifferenceObject $StagingPorts |
            Where-Object SideIndicator -eq '<=' |
            ForEach-Object InputObject
    )
    $AddedDiff = @(Compare-Object -CaseSensitive `
        -ReferenceObject $ExpectedAddedWrapperPorts `
        -DifferenceObject $AddedPorts)
    if ($AddedDiff.Count -ne 0 -or $RemovedPorts.Count -ne 0) {
        $ContractFailures.Add(
            'PG2L50H wrapper port delta is not the approved five additions'
        )
    }

    foreach ($Required in @(
            '(?m)^\s*GTP_INBUFDS\s+refclk_inbuf\b',
            '\.O\s*\(\s*ref_clk\s*\)',
            '\.I\s*\(\s*ref_clk_p\s*\)',
            '\.IB\s*\(\s*ref_clk_n\s*\)'
        )) {
        if ($StagingWrapperText -notmatch $Required) {
            $ContractFailures.Add("PG2L50H differential refclk contract missing '$Required'")
        }
    }

    $CanonicalConnections = Get-DdrInstanceConnections -Text $CanonicalWrapperText
    $StagingConnections = Get-DdrInstanceConnections -Text $StagingWrapperText
    $ConnectionNames = @(
        Compare-Object -CaseSensitive `
            -ReferenceObject @($CanonicalConnections.Keys) `
            -DifferenceObject @($StagingConnections.Keys)
    )
    if ($ConnectionNames.Count -ne 0) {
        $ContractFailures.Add('I_ips_ddr_top connection names changed')
    } else {
        foreach ($Port in $CanonicalConnections.Keys) {
            $ExpectedSignal = $CanonicalConnections[$Port]
            if ($Port -ceq 'ref_clk') {
                $ExpectedSignal = 'ref_clk'
                if ($CanonicalConnections[$Port] -cne 'free_clk') {
                    $ContractFailures.Add(
                        'Canonical I_ips_ddr_top ref_clk is no longer free_clk'
                    )
                }
            }
            if ($StagingConnections[$Port] -cne $ExpectedSignal) {
                $ContractFailures.Add(
                    "I_ips_ddr_top connection '$Port' changed unexpectedly"
                )
            }
        }
    }

    return $ContractFailures
}

function Invoke-NegativeSelfTest {
    $Core = @'
module ddr3(
    input ref_clk,
    output axi_wready,
    output axi_wusero_last,
    output axi_rvalid,
    output axi_rlast,
    output ddr_init_done,
    output core_clk
);
'@
    $CanonicalWrapper = @'
module test_ddr(
    input free_clk,
    input rst_board,
    output err_flag_led
);
ddr3 #(
    .P(1)
) I_ips_ddr_top(
    .ref_clk(free_clk), .axi_wready(axi_wready)
);
'@
    $StagingWrapper = @'
module test_ddr(
    input ref_clk_p,
    input ref_clk_n,
    input free_clk,
    input rst_board,
    output pll_lock,
    output ddrphy_cpd_lock,
    output ddr_init_done,
    output err_flag_led
);
GTP_INBUFDS refclk_inbuf(.O(ref_clk), .I(ref_clk_p), .IB(ref_clk_n));
ddr3 #(
    .P(1)
) I_ips_ddr_top(
    .ref_clk(ref_clk), .axi_wready(axi_wready)
);
'@

    $GoodFailures = @(Get-WrapperContractFailures `
        -CanonicalCoreText $Core -CanonicalWrapperText $CanonicalWrapper `
        -StagingCoreText $Core -StagingWrapperText $StagingWrapper)
    if ($GoodFailures.Count -ne 0) {
        Add-Failure (
            'D3-0-M self-test rejected the approved contract: ' +
            ($GoodFailures -join '; ')
        )
    }

    $WrongClock = $StagingWrapper.Replace('.ref_clk(ref_clk)', `
        '.ref_clk(free_clk)')
    if (@(Get-WrapperContractFailures `
            -CanonicalCoreText $Core -CanonicalWrapperText $CanonicalWrapper `
            -StagingCoreText $Core -StagingWrapperText $WrongClock).Count -eq 0) {
        Add-Failure 'D3-0-M self-test did not reject refclk topology drift'
    }

    $MissingPort = [regex]::Replace(
        $StagingWrapper,
        '(?m)^\s*input ref_clk_n,\s*\r?\n',
        ''
    )
    if (@(Get-WrapperContractFailures `
            -CanonicalCoreText $Core -CanonicalWrapperText $CanonicalWrapper `
            -StagingCoreText $Core -StagingWrapperText $MissingPort).Count -eq 0) {
        Add-Failure 'D3-0-M self-test did not reject wrapper port drift'
    }

    $CoreWithRready = $Core.Replace('output axi_rvalid', `
        'input axi_rready, output axi_rvalid')
    if (@(Get-WrapperContractFailures `
            -CanonicalCoreText $Core -CanonicalWrapperText $CanonicalWrapper `
            -StagingCoreText $CoreWithRready `
            -StagingWrapperText $StagingWrapper).Count -eq 0) {
        Add-Failure 'D3-0-M self-test did not reject axi_rready'
    }
}

$CanonicalCoreExists = Require-File -Path $CanonicalCorePath `
    -Description 'canonical DDR3 core'
$CanonicalWrapperExists = Require-File -Path $CanonicalWrapperPath `
    -Description 'canonical DDR3 wrapper'
$ReviewExists = Require-File -Path $ReviewPath `
    -Description 'D3-0-M PG2L50H staging review'
$PortMapExists = Require-File -Path $PortMapPath `
    -Description 'D3-A port map'

if ($ReviewExists) {
    $ReviewText = Get-Content -Raw -Encoding UTF8 -LiteralPath $ReviewPath
    foreach ($Required in @(
            'ref_clk_p/ref_clk_n',
            'GTP_INBUFDS',
            'free_clk.*ref_clk',
            'pll_lock.*ddrphy_cpd_lock.*ddr_init_done',
            'D3-A.*blocked',
            'PG2L50H-6IFBG484'
        )) {
        if ($ReviewText -notmatch $Required) {
            Add-Failure "D3-0-M review is missing '$Required'"
        }
    }
}
if ($PortMapExists) {
    $PortMapText = Get-Content -Raw -Encoding UTF8 -LiteralPath $PortMapPath
    foreach ($Required in @(
            'D3A_PG2L50H_STAGING_REVIEW\.md',
            'ref_clk_p/ref_clk_n',
            'D3-A.*blocked'
        )) {
        if ($PortMapText -notmatch $Required) {
            Add-Failure "D3-A port map is missing '$Required'"
        }
    }
}

if ($CanonicalCoreExists -and $CanonicalWrapperExists) {
    $CanonicalCoreText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $CanonicalCorePath
    $CanonicalWrapperText = Get-Content -Raw -Encoding UTF8 `
        -LiteralPath $CanonicalWrapperPath
    if (@(Get-ModulePorts -Text $CanonicalWrapperText `
            -ModuleName 'test_ddr').Count -ne 21) {
        Add-Failure 'Canonical DDR3 wrapper no longer has 21 ports'
    }
    $CanonicalConnections = Get-DdrInstanceConnections `
        -Text $CanonicalWrapperText
    if ($CanonicalConnections['ref_clk'] -cne 'free_clk') {
        Add-Failure 'Canonical DDR3 wrapper refclk contract changed'
    }
}

if ($SelfTest) {
    Invoke-NegativeSelfTest
}

if (-not $StaticOnly) {
    if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
        $StagingRoot = Join-Path $ProjectRoot 'build\ipgen\pg2l50h'
    } elseif (-not [IO.Path]::IsPathRooted($StagingRoot)) {
        $StagingRoot = Join-Path $ProjectRoot $StagingRoot
    }
    $StagingRoot = [IO.Path]::GetFullPath($StagingRoot)
    $StagingCorePath = Join-Path $StagingRoot 'ddr3.v'
    $StagingWrapperPath = Join-Path $StagingRoot `
        'example_design\rtl\test_ddr.v'
    $StagingIdfPath = Join-Path $StagingRoot 'ddr3.idf'

    $StagingCoreExists = Require-File -Path $StagingCorePath `
        -Description 'PG2L50H staging DDR3 core'
    $StagingWrapperExists = Require-File -Path $StagingWrapperPath `
        -Description 'PG2L50H staging DDR3 wrapper'
    $StagingIdfExists = Require-File -Path $StagingIdfPath `
        -Description 'PG2L50H staging DDR3 IDF'

    if ($CanonicalCoreExists -and $CanonicalWrapperExists -and
        $StagingCoreExists -and $StagingWrapperExists) {
        $StagingCoreText = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $StagingCorePath
        $StagingWrapperText = Get-Content -Raw -Encoding UTF8 `
            -LiteralPath $StagingWrapperPath
        foreach ($Failure in @(Get-WrapperContractFailures `
                -CanonicalCoreText $CanonicalCoreText `
                -CanonicalWrapperText $CanonicalWrapperText `
                -StagingCoreText $StagingCoreText `
                -StagingWrapperText $StagingWrapperText)) {
            Add-Failure $Failure
        }
        if (@(Get-ModulePorts -Text $StagingWrapperText `
                -ModuleName 'test_ddr').Count -ne 26) {
            Add-Failure 'PG2L50H staging wrapper does not have 26 ports'
        }
    }

    if ($StagingIdfExists) {
        try {
            [xml]$StagingIdf = Get-Content -Raw -Encoding UTF8 `
                -LiteralPath $StagingIdfPath
            $Header = $StagingIdf.ip_inst.header
            if ([string]$Header.family -cne 'Logos2' -or
                [string]$Header.device -cne 'PG2L50H' -or
                [string]$Header.package -cne 'FBG484' -or
                [string]$Header.speedgrade -cne '-6' -or
                [string]$Header.generator.version -cne '2022.2-SP6.4' -or
                [string]$Header.generator.build -cne '146967') {
                Add-Failure 'PG2L50H staging IDF header does not match SP6.4'
            }
            $DeviceFlag = @(
                $StagingIdf.ip_inst.param_list.param |
                    Where-Object { [string]$_.name -ceq 'DEVICE_100H_EN' }
            )
            if ($DeviceFlag.Count -ne 1 -or
                [string]$DeviceFlag[0].value -cne 'false') {
                Add-Failure 'PG2L50H staging DEVICE_100H_EN is not false'
            }
        } catch {
            Add-Failure "PG2L50H staging IDF parse failed: $($_.Exception.Message)"
        }
    }
}

if ($Failures.Count -gt 0) {
    throw "D3-0-M staging contract gate failed:`n - $($Failures -join "`n - ")"
}

if ($SelfTest) {
    Write-Host 'INFO: D3-0-M negative self-tests passed'
}
if ($StaticOnly) {
    Write-Host 'INFO: D3-0-M static contract passed'
} else {
    Write-Host 'INFO: D3-0-M PG2L50H staging contract audit passed'
}
