set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_ONLY"
foreach cmd {open_project add_design define_current_design export_fdc} {
    if {[llength [info commands $cmd]]} {
        puts "HELP_BEGIN $cmd"
        set rc [catch [list $cmd -help] result]
        puts "HELP_END $cmd rc=$rc result=$result"
    } else {
        puts "COMMAND_ABSENT $cmd"
    }
}
puts "NO_DESIGN_DB_LOADED"
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_COMPLETE"
