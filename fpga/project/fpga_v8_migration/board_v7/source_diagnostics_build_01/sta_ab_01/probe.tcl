set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
foreach cmd {read_adf read_db load_db read_fdc read_sdc set_clock_groups set_max_delay set_false_path get_pins get_clocks all_clocks report_timing} {
 puts "PROBE $cmd exists=[info commands $cmd]"
 if {[llength [info commands $cmd]]} {set rc [catch [list $cmd -help] result]; puts "PROBE_RC $cmd $rc $result"}
}
puts "COMMANDS [info commands *read*] [info commands *load*] [info commands *db*] [info commands *constraint*]"
