param([ValidateSet('actual','ge','ctc','ctc_fixed')][string]$Case='actual')
$ErrorActionPreference='Stop'
$bin='C:\modeltech64_10.6e\win64'
$root=(Resolve-Path "$PSScriptRoot\..\..\..").Path
$tx="$root\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl"
$rx="$root\project\source\sfp"
Push-Location $PSScriptRoot
try {
    $lib="work_$Case"
    if(Test-Path $lib) { Remove-Item -Recurse -Force $lib }
    & "$bin\vlib.exe" $lib
    if($LASTEXITCODE) { throw 'vlib failed' }
    $txfile="$tx\sfp_video_tx.v"
    $defs=@()
    $argsim=@()
    if($Case -like 'ctc*') { $txfile="$tx\sfp_video_tx_ctc.v"; $defs=@('+define+CTC_SOURCE'); $argsim=@('+RESET_NS=109') }
    if($Case -eq 'ge') { $argsim=@('+GE') }
    if($Case -eq 'ctc_fixed') { $argsim+=@('+FIX_POP') }
    # Explicit configuration binds each endpoint to its own production FIFO.
    $txlib="tx_$Case"
    if(Test-Path $txlib) { Remove-Item -Recurse -Force $txlib }
    & "$bin\vlib.exe" $txlib
    & "$bin\vlog.exe" -work $txlib "$tx\video_async_fifo.v" $txfile
    if($LASTEXITCODE) { throw 'TX compile failed' }
    & "$bin\vlog.exe" -sv -work $lib @defs "$rx\video_async_fifo.v" "$rx\sfp_video_rx.v" "$rx\sfp_rx_cam_if.v" tb_sfp_full.sv
    if($LASTEXITCODE) { throw 'RX/TB compile failed' }
    & "$bin\vlog.exe" -sv -work $lib "+define+TX_LIB=$txlib" "+define+RX_LIB=$lib" full_config.sv
    if($LASTEXITCODE) { throw 'Configuration compile failed' }
    & "$bin\vsim.exe" -c -lib $lib full_config @argsim -l "$Case.log" -do 'onbreak {quit -code 1 -f}; onerror {quit -code 1 -f}; run -all; quit -code 0 -f'
    if($LASTEXITCODE -or !(Select-String -Path "$Case.log" -SimpleMatch 'TB_PASS full' -Quiet)) { throw "Simulation failed: $Case (see $Case.log)" }
} finally { Pop-Location }
