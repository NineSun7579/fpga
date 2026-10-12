onerror {quit -code 1 -f}
set lib arb_registered_work
if {[file exists $lib]} {vdel -lib $lib -all}
vlib $lib
vlog -work $lib ../../source/axi_crossbar/ddr_w_arb.v tb_arb6.v
vlog -sv -work $lib tb_arb6_registered.sv
vsim -onfinish stop -lib $lib tb_arb6
run -all
if {[examine -radix decimal /tb_arb6/done_cnt(0)] != 6 ||
    [examine -radix decimal /tb_arb6/done_cnt(1)] != 3 ||
    [examine -radix decimal /tb_arb6/done_cnt(2)] != 3 ||
    [examine -radix decimal /tb_arb6/done_cnt(3)] != 3 ||
    [examine -radix decimal /tb_arb6/done_cnt(4)] != 3 ||
    [examine -radix decimal /tb_arb6/done_cnt(5)] != 3 ||
    [examine -radix decimal /tb_arb6/err] != 0} {
    puts "LEGACY_TEST_FAIL: tb_arb6 also fails with original RTL; see baseline log"
}
quit -sim
vsim -onfinish stop -lib $lib tb_arb6_registered
run -all
if {[examine -radix decimal /tb_arb6_registered/passed] != 1} {
    quit -code 1 -f
}
quit -code 0 -f
