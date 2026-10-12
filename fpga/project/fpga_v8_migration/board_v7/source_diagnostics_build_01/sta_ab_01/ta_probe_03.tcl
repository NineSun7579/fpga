set_arch -input_db_file {C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/source_diagnostics_build_01/sta_ab_01/A_original_inputs/synthesis.adf}
puts "TA_COMMANDS [info commands]"
puts "TA_CLOCKS [all_clocks]"
foreach cmd {set_arch report_timing read_sdc read_fdc report_clock report_exceptions get_pins} {
 puts "TA_CMD $cmd [info commands $cmd]"
 if {[llength [info commands $cmd]]} {catch [list $cmd -help] result;puts $result}
}
puts "TA_PROBE_DONE"
exit
