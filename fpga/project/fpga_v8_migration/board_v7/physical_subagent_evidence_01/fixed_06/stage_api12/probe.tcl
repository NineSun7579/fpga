set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
foreach cmd {define_current_design define_scope_collection save_adif load read export_fdc dev_map} {
 puts "STAGE_API12_BEGIN $cmd"
 set rc [catch {$cmd -help} value]
 puts "STAGE_API12_RESULT $cmd $rc $value"
}
