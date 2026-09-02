# PDS 2022.2-SP6.4 constraint-object audit probe.
# Run after the PCIe design has been loaded and compiled in pds_shell.
# This probe reports object resolution only; it does not approve exceptions.

set out_file ""
if {[info exists ::env(PCIE_CONSTRAINT_PROBE_OUT)]} {
    set out_file $::env(PCIE_CONSTRAINT_PROBE_OUT)
}
if {$out_file eq ""} {
    set out_file "build/logs/pcie-constraint-object-probe.txt"
}
file mkdir [file dirname $out_file]
set fh [open $out_file w]

proc emit {fh text} {
    puts $text
    puts $fh $text
}

emit $fh "PCIe constraint object probe"
emit $fh "PDS version: [info patchlevel]"
emit $fh ""

foreach clock_name {pclk pclk_div2 ref_clk} {
    set objects [get_clocks $clock_name]
    emit $fh "CLOCK $clock_name COUNT [llength $objects] OBJECTS $objects"
}

foreach group_name {group_1 group_2 group_3} {
    set groups [get_clock_groups $group_name]
    emit $fh "CLOCK_GROUP $group_name COUNT [llength $groups] OBJECTS $groups"
}

emit $fh "EXCEPTIONS_BEGIN"
report_exceptions
emit $fh "EXCEPTIONS_END"
close $fh
puts "INFO: constraint object probe wrote $out_file"
