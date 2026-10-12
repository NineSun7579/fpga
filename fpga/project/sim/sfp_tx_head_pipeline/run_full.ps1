param([ValidateSet('candidate','production')][string]$Case='candidate')
$ErrorActionPreference='Stop'
$bin='C:\modeltech64_10.6e\win64'
$root=(Resolve-Path "$PSScriptRoot\..\..\..").Path
$rx="$root\project\source\sfp"
$tx="$PSScriptRoot\candidate"
if($Case -eq 'production') { $tx="$root\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl" }
$txlib="tx_full_$Case"
$rxlib="work_full_$Case"
$log="full_$Case.log"
Push-Location $PSScriptRoot
try {
    foreach($lib in @($txlib,$rxlib)) {
        if(Test-Path $lib) { Remove-Item -Recurse -Force $lib }
        & "$bin\vlib.exe" $lib
        if($LASTEXITCODE) { throw 'vlib failed' }
    }
    & "$bin\vlog.exe" -work $txlib "$tx\video_async_fifo.v" "$tx\sfp_video_tx.v"
    if($LASTEXITCODE) { throw 'TX compile failed' }
    # Reuse the existing two-frame, actual-merge 1280x480 test and its
    # unchanged 100H decoder/splitter, but isolate libraries and all outputs.
    & "$bin\vlog.exe" -sv -work $rxlib "$rx\video_async_fifo.v" "$rx\sfp_video_rx.v" "$rx\sfp_rx_cam_if.v" "$PSScriptRoot\..\sfp_full\tb_sfp_full.sv"
    if($LASTEXITCODE) { throw 'RX/TB compile failed' }
    & "$bin\vlog.exe" -sv -work $rxlib "+define+TX_LIB=$txlib" "+define+RX_LIB=$rxlib" "$PSScriptRoot\..\sfp_full\full_config.sv"
    if($LASTEXITCODE) { throw 'config compile failed' }
    & "$bin\vsim.exe" -c -lib $rxlib full_config -l $log -do 'onbreak {quit -code 1 -f}; onerror {quit -code 1 -f}; run -all; quit -code 0 -f'
    if($LASTEXITCODE -or !(Select-String -Path $log -SimpleMatch -Pattern 'TB_PASS full' -Quiet)) { throw 'Full-size continuous regression failed' }
} finally { Pop-Location }
