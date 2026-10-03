if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work ../../source/axi_crossbar/ddr_w_arb.v
vlog -work work tb_arb6.v
vsim -c -lib work tb_arb6
run -all
quit -f
