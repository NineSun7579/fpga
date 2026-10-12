$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    $cases=@(
        @{Name='drop200_tail';Script='set MODE 7;'},
        @{Name='partial_phase';Script='set MODE 8; set SHIFT 7.3; set PB 11.920;'},
        @{Name='early_vs';Script='set MODE 9; set SHIFT 1.7;'},
        @{Name='odd_href';Script='set MODE 10; set SHIFT 5.9;'}
    )
    foreach($case in $cases) {
        & C:\modeltech64_10.6e\win64\vsim.exe -c -l ($case.Name+'.log') -do ($case.Script+' do run.do')
        if($LASTEXITCODE -ne 0) {throw ($case.Name+': simulator failed')}
        if(!(Select-String -Path ($case.Name+'.log') -SimpleMatch 'TEST PASS' -Quiet)) {
            throw ($case.Name+': scoreboard failed')
        }
    }
} finally {Pop-Location}
