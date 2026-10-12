set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
open_project {copied/project.pds}
puts "IO_BANK_CONTEXT_PROJECT_OPENED"
set pending [list ::]
set found {}
while {[llength $pending]} {
    set ns [lindex $pending 0]
    set pending [lrange $pending 1 end]
    foreach child [namespace children $ns] { lappend pending $child }
    foreach cmd [info commands ${ns}::*] { lappend found $cmd }
}
foreach cmd [lsort -unique $found] {
    puts "CONTEXT_COMMAND $cmd"
    if {[regexp -nocase {bank|pinout|pad|prop|attr|report|export|site|device|inspect|query|db} $cmd]} {
        puts "CONTEXT_CANDIDATE $cmd"
    }
}
export_fdc -file {context_roundtrip.fdc}
puts "IO_BANK_CONTEXT_EXPORT_COMPLETE"
