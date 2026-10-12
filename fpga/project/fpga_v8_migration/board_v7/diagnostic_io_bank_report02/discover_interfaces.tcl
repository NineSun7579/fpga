set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "IO_BANK_DIAGNOSTIC_DISCOVERY_ONLY"
set pending [list ::]
set found {}
while {[llength $pending]} {
    set ns [lindex $pending 0]
    set pending [lrange $pending 1 end]
    foreach child [namespace children $ns] {
        lappend pending $child
    }
    foreach cmd [info commands ${ns}::*] {
        lappend found $cmd
    }
}
foreach cmd [lsort -unique $found] {
    puts "COMMAND $cmd"
    if {[regexp -nocase {bank|pin|pad|port|package|io|prop|attr|report|export|write|dump|save|load|read|open|db|design|site|device|inspect|query|print|list|help} $cmd]} {
        puts "CANDIDATE $cmd"
    }
}
foreach cmd {export_fdc .switch_db get_pins get_cells get_ports} {
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
