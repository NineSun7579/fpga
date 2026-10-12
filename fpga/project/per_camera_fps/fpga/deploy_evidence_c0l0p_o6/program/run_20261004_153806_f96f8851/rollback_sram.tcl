if {[catch {
cfg_scan_chain
set motion_log [open "C:/Users/NineSun/Desktop/ov56401/project/per_camera_fps/fpga/deploy_evidence_c0l0p_o6/program/run_20261004_153806_f96f8851/log/cfg.log" r]
set motion_text [read $motion_log]
close $motion_log
set motion_start [string last "Executing : cfg_scan_chain\n" $motion_text]
if {$motion_start < 0} {error "MOTION_GUARD: scan log format not established"}
set motion_scan [string range $motion_text $motion_start end]
if {[string first "Executing : cfg_scan_chain successfully." $motion_scan] < 0} {
    error "MOTION_GUARD: scan has not completed successfully"
}
set motion_devices [regexp -all -inline -line {^PG[A-Z0-9]+(?:-[A-Za-z0-9]+)?\r?$} $motion_scan]
set motion_device_count [regexp -all {This device configure situation \(done bit\):} $motion_scan]
if {[llength $motion_devices] != 1 || $motion_device_count != 1 || [string trim [lindex $motion_devices 0]] ne "PG2L100H"} {
    error "MOTION_GUARD: expected exactly one PG2L100H, got $motion_devices"
}
cfg_assign_file -file "C:/Users/NineSun/Desktop/ov56401/project/bitstream_six_recovery_20261002_192245/top.sbit" -device_index 0
cfg_program -device_index 0
cfg_scan_chain
set motion_log [open "C:/Users/NineSun/Desktop/ov56401/project/per_camera_fps/fpga/deploy_evidence_c0l0p_o6/program/run_20261004_153806_f96f8851/log/cfg.log" r]
set motion_text [read $motion_log]
close $motion_log
set motion_start [string last "Executing : cfg_scan_chain\n" $motion_text]
if {$motion_start < 0} {error "MOTION_GUARD: scan log format not established"}
set motion_scan [string range $motion_text $motion_start end]
if {[string first "Executing : cfg_scan_chain successfully." $motion_scan] < 0} {
    error "MOTION_GUARD: scan has not completed successfully"
}
set motion_devices [regexp -all -inline -line {^PG[A-Z0-9]+(?:-[A-Za-z0-9]+)?\r?$} $motion_scan]
set motion_device_count [regexp -all {This device configure situation \(done bit\):} $motion_scan]
if {[llength $motion_devices] != 1 || $motion_device_count != 1 || [string trim [lindex $motion_devices 0]] ne "PG2L100H"} {
    error "MOTION_GUARD: expected exactly one PG2L100H, got $motion_devices"
}
if {[string first "This device configure situation (done bit): 1" $motion_scan] < 0} {
    error "MOTION_GUARD: final target DONE is not asserted"
}

} motion_error]} {
error "MOTION_GUARD: $motion_error"
}
