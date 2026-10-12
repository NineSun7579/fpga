puts {TA_ACTUAL_COMMANDS_BEGIN}
puts [lsort [info commands]]
puts {TA_ACTUAL_COMMANDS_END}
if {[llength [info commands help]]} {help report_timing; help save_adif; help set_clock_groups}
exit
