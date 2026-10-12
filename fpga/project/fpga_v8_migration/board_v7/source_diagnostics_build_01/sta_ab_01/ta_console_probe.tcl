set out [open {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01/ta_console_probe.txt} w]
puts $out "COMMANDS [info commands]"
foreach cmd {report_timing get_pins get_clocks all_clocks export_fdc save_constraint} {
 puts $out "CMD $cmd [info commands $cmd]"
 if {[llength [info commands $cmd]]} {set rc [catch [list $cmd -help] result];puts $out "RC $rc $result"}
}
puts $out "CLOCKS [all_clocks]"
puts $out "PIN [get_pins {source_diagnostics/cameras[0].source/mailbox[0]/CLK}]"
close $out
