$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    $cases=@(
        @{Name='full62';Script=''},
        @{Name='extra62';Script='set EXTRA 1;'},
        @{Name='missing62';Script='set MODE 1;'},
        @{Name='partial62';Script='set MODE 2;'},
        @{Name='mixed62';Script='set MODE 3;'},
        @{Name='late62';Script='set MODE 4;'},
        @{Name='slow62';Script='set PB 11.920;'},
        @{Name='absent62';Script='set MODE 5;'},
        @{Name='frame_missing62';Script='set MODE 6;'}
    )
    foreach($case in $cases) {
        $logName='production_'+$case.Name+'.log'
        $simScript='set MERGE ../../../../ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/cam2_merge.v; '+$case.Script+' do run.do'
        & C:\modeltech64_10.6e\win64\vsim.exe -c -l $logName -do $simScript
        if($LASTEXITCODE -ne 0) {throw ($case.Name+': simulator failed')}
        if(!(Select-String -Path $logName -SimpleMatch 'TEST PASS' -Quiet)) {
            throw ($case.Name+': scoreboard failed')
        }
    }
} finally {Pop-Location}
