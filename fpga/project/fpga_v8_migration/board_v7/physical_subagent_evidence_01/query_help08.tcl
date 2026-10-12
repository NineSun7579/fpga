set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
foreach cmd {get_pins get_cells get_nets get_clocks sizeof_collection get_object_name get_attribute query_objects foreach_in_collection read_db read_adf read_sdc read_fdc add_constraint report_timing} {
 puts "AVAILABLE $cmd [info commands $cmd]"
 if {[llength [info commands $cmd]]} {
  puts "HELP_BEGIN $cmd"
  set rc [catch [list $cmd -help] result]
  puts "HELP_END $cmd rc=$rc result=$result"
 }
}
puts "DB_COMMANDS [info commands *db*]"
puts "COLLECTION_COMMANDS [info commands *collection*]"
puts "OBJECT_COMMANDS [info commands *object*]"
