onerror {quit -code 1}
set f [open hierarchy.txt w]
foreach i [find instances -recursive /*] {puts $f $i}
close $f
run -all
quit -f
