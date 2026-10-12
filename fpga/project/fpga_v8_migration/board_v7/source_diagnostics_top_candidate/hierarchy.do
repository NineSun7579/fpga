onerror {quit -code 1}
set f [open hierarchy.txt w]
foreach inst [find instances -recursive /*] {puts $f $inst}
close $f
set f [open diagnostics_signals.txt w]
foreach sig [find signals -recursive /tb_elab/dut/source_diagnostics/*] {puts $f $sig}
foreach cam {ov5640_top cam2_ov5640_top cam3_ov5640_top cam4_ov5640_top} {
    foreach sig [find signals -recursive /tb_elab/dut/$cam/ov5640/*] {puts $f $sig}
}
close $f
run 0 ns
puts TOP_ELAB_PASS
quit -f
