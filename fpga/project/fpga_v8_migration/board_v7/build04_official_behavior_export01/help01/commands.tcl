set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484
puts "COMMANDS [lsort [info commands]]"
foreach c {.switch_db .verilog.print gen_netlist create_vlog_netlist} {puts "HELP_BEGIN $c"; puts "HELP_RESULT [catch {help $c} result] $result"; if {[llength [info commands $c]]} {puts "DASH_HELP_RESULT [catch {$c -help} result] $result"}; puts "HELP_END $c"}
