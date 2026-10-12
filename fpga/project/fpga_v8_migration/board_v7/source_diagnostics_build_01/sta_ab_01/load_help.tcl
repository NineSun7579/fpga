set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
foreach cmd {read load add_constraint remove_constraint report_timing get_cells get_property get_attribute sizeof_collection get_object_name} {
 puts "PROBE $cmd exists=[info commands $cmd]"
 if {[llength [info commands $cmd]]} {set rc [catch [list $cmd -help] result]; puts "PROBE_RC $cmd $rc $result"}
}
