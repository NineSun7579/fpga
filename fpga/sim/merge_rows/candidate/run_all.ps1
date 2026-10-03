$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    & C:\Users\NineSun\anaconda3\python.exe prepare.py
    $cases=@(
        @{Name='full62';Script='do run.do'},
        @{Name='extra62';Script='set EXTRA 1; do run.do'},
        @{Name='missing62';Script='set MODE 1; do run.do'},
        @{Name='partial62';Script='set MODE 2; do run.do'},
        @{Name='mixed62';Script='set MODE 3; do run.do'},
        @{Name='late62';Script='set MODE 4; do run.do'},
        @{Name='slow62';Script='set PB 11.920; do run.do'},
        @{Name='absent62';Script='set MODE 5; do run.do'},
        @{Name='frame_missing62';Script='set MODE 6; do run.do'}
    )
    foreach($case in $cases) {
        & C:\modeltech64_10.6e\win64\vsim.exe -c -l ($case.Name+'.log') -do $case.Script
        if($LASTEXITCODE -ne 0) {throw ($case.Name+': simulator failed')}
        if(!(Select-String -Path ($case.Name+'.log') -SimpleMatch 'TEST PASS' -Quiet)) {
            throw ($case.Name+': scoreboard failed')
        }
    }
} finally {Pop-Location}
