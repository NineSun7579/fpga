set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_ONLY"
foreach cmd {show_device def_inst_site define_attribute} {
    if {[llength [info commands $cmd]]} {
        puts "HELP_BEGIN $cmd"
        set rc [catch [list $cmd -help] result]
        puts "HELP_END $cmd rc=$rc result=$result"
    }
}
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_COMPLETE"
