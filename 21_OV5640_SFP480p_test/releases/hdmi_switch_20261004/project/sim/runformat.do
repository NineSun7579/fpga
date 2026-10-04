onerror {quit -code 1}
# Resume the macro after $finish; check an explicit pass flag before exiting.
onbreak {resume}
# Questa's macro interpreter reports its own E:/mtitcl/vsim as info script.
# Invoke from project/sim, as for the existing integration scripts.
set simdir [pwd]
set root [file dirname $simdir]
set snapshot [file join $root format_sim_[clock format [clock seconds] -format %Y%m%d_%H%M%S]_[pid]]
file mkdir $snapshot
# Compile immutable copies: the FIFO/timing agent may edit live sources.
foreach name {video_reset_sync.v video_mode_keys.v video_mode_switch.v hdmi_720p_capture.v video_async_fifo.v sfp_video_tx.v} {
    file copy [file join $root source rtl $name] [file join $snapshot $name]
}
file copy [file join [file dirname $root] receiver sfp sfp_video_rx.v] [file join $snapshot sfp_video_rx.v]
file copy [file join $simdir input_clock_model.v] [file join $snapshot input_clock_model.v]
foreach name {tb_capture_formats.sv tb_hdmi_modes.sv} {
    file copy [file join $simdir $name] [file join $snapshot $name]
}
set hashcmd "Get-ChildItem -LiteralPath '$snapshot' -File | Get-FileHash -Algorithm SHA256 | Format-List Path,Hash"
set hashes [exec powershell.exe -NoProfile -Command $hashcmd]
set manifest [open [file join $snapshot source_sha256.txt] w]
puts $manifest $hashes
close $manifest
puts "IMMUTABLE FORMAT SNAPSHOT: $snapshot"
puts $hashes
cd $snapshot
vlib work_format
vmap work [file join $snapshot work_format]
vlog input_clock_model.v
vlog -sv video_reset_sync.v video_mode_keys.v video_mode_switch.v hdmi_720p_capture.v video_async_fifo.v sfp_video_tx.v sfp_video_rx.v tb_capture_formats.sv tb_hdmi_modes.sv
set testtop tb_capture_formats
if {[info exists env(FORMAT_TEST_TOP)]} {set testtop $env(FORMAT_TEST_TOP)}
vsim -voptargs=+acc -onfinish stop -t 1ps work.$testtop
run -all
if {[examine -radix unsigned /$testtop/test_pass] != 1} {quit -code 1}
# Optional existing mode/debounce regression against the same snapshot.
if {[info exists env(FORMAT_RUN_MODES)] && $env(FORMAT_RUN_MODES)==1} {
    quit -sim
    vsim -voptargs=+acc -onfinish stop -t 1ps work.tb_hdmi_modes
    run -all
    if {[examine -radix unsigned /tb_hdmi_modes/test_pass] != 1} {quit -code 1}
}
quit -code 0
