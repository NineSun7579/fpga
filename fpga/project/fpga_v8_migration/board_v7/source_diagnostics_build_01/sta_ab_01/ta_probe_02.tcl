puts "TA_COMMANDS [info commands]"
foreach cmd {set_arch read_design load_design read_db load_db report_timing} {
 puts "TA_CMD $cmd [info commands $cmd]"
 if {[llength [info commands $cmd]]} {catch [list $cmd -help] result;puts $result}
}
puts "TA_PROBE_DONE"
exit
