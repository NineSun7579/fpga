$ErrorActionPreference = 'Stop'
$simBin = 'C:\modeltech64_10.6e\win64\vsim.exe'
$pythonBin = 'C:\Users\NineSun\anaconda3\python.exe'
Push-Location $PSScriptRoot
try {
    & $pythonBin prepare_candidate.py
    $cases = @(
        @{ Name='baseline'; Script='do run.do'; Expected='TEST PASS' },
        @{ Name='overscan_original'; Script='set EXTRA 1; set MERGE cam2_merge_before_cap_fix.v; do run.do'; Expected='TEST FAIL' },
        @{ Name='overscan_production'; Script='set EXTRA 1; do run.do'; Expected='TEST PASS' },
        @{ Name='overscan_fixed'; Script='set EXTRA 1; set MERGE cam2_merge_cap_candidate.v; do run.do'; Expected='TEST PASS' },
        @{ Name='burst84_vts2820'; Script='set PA 11.9045; set PB 11.900; set VTS 2820; do run.do'; Expected='TEST FAIL' },
        @{ Name='burst84_100m'; Script='set PA 11.9045; set PB 11.900; set PO 10.0; do run.do'; Expected='TEST PASS' },
        @{ Name='burst84_125m'; Script='set PA 11.9045; set PB 11.900; set PO 8.0; do run.do'; Expected='TEST PASS' },
        @{ Name='overscan84_125m'; Script='set EXTRA 1; set PA 11.9045; set PB 11.900; set PO 8.0; do run.do'; Expected='TEST PASS' },
        @{ Name='overscan84_100m'; Script='set EXTRA 1; set PA 11.9045; set PB 11.900; set PO 10.0; do run.do'; Expected='TEST PASS' }
    )
    foreach ($case in $cases) {
        & $simBin -c -l ($case.Name + '.log') -do $case.Script
        if ($LASTEXITCODE -ne 0) { throw ($case.Name + ': ModelSim error') }
        if (!(Select-String -Path ($case.Name + '.log') -SimpleMatch $case.Expected -Quiet)) {
            throw ($case.Name + ': expected ' + $case.Expected)
        }
    }
} finally { Pop-Location }
