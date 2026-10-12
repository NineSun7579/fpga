set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_ONLY"
foreach pattern {*bank* *Bank* *BANK* *package* *pinout* *report* *load* *read* *db* *property* *attribute*} {
    puts "COMMAND_PATTERN $pattern [lsort [info commands $pattern]]"
}
foreach cmd {get_pins get_cells get_ports get_attribute get_property read_db read_adf report_io report_pinout report_package} {
    if {[llength [info commands $cmd]]} {
        puts "HELP_BEGIN $cmd"
        set rc [catch [list $cmd -help] result]
        puts "HELP_END $cmd rc=$rc result=$result"
    } else {
        puts "COMMAND_ABSENT $cmd"
    }
}
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_COMPLETE"
