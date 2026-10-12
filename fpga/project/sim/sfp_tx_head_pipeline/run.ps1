param([ValidateSet('candidate','production','original')][string]$Case='candidate')
$ErrorActionPreference='Stop'
$bin='C:\modeltech64_10.6e\win64'
$root=(Resolve-Path "$PSScriptRoot\..\..\..").Path
$prod="$root\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl"
$tx=$prod
if($Case -eq 'candidate') { $tx="$PSScriptRoot\candidate" }
if($Case -eq 'original') { $tx="$PSScriptRoot\archived_original" }
Push-Location $PSScriptRoot
try {
    $txlib="tx_$Case"
    $rxlib="work_$Case"
    foreach($lib in @($txlib,$rxlib)) {
        if(Test-Path $lib) { Remove-Item -Recurse -Force $lib }
        & "$bin\vlib.exe" $lib
        if($LASTEXITCODE) { throw 'vlib failed' }
    }
    & "$bin\vlog.exe" -work $txlib "$tx\video_async_fifo.v" "$tx\sfp_video_tx.v"
    if($LASTEXITCODE) { throw 'TX compile failed' }
    & "$bin\vlog.exe" -sv -work $rxlib "$root\project\source\sfp\sfp_video_rx.v" tb_tx_recovery.sv
    if($LASTEXITCODE) { throw 'RX/TB compile failed' }
    & "$bin\vlog.exe" -sv -work $rxlib "+define+TX_LIB=$txlib" "+define+RX_LIB=$rxlib" recovery_config.sv
    if($LASTEXITCODE) { throw 'config compile failed' }
    & "$bin\vsim.exe" -c -lib $rxlib recovery_config -l "$Case.log" -do 'onbreak {quit -code 1 -f}; onerror {quit -code 1 -f}; run -all; quit -code 0 -f'
    $simExit=$LASTEXITCODE
    if($Case -ne 'original') {
        if($simExit -or !(Select-String -Path "$Case.log" -SimpleMatch -Pattern 'TB_PASS recovery' -Quiet)) { throw 'Candidate failed' }
    } else {
        if(!(Select-String -Path "$Case.log" -SimpleMatch -Pattern 'TB_FAIL recovery' -Quiet)) { throw 'Negative control did not fail' }
        if(!(Select-String -Path "$Case.log" -Pattern 'RECOVERY postfault_payload_words=[1-9][0-9]*' -Quiet)) { throw 'Negative control did not expose the post-fault payload fault' }
        Write-Output 'NEGATIVE_CONTROL_PASS: unmodified production fails the recovery contract.'
    }
} finally { Pop-Location }
