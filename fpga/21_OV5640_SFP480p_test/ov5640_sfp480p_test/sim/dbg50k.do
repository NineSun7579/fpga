if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work ../source/rtl/cam2_merge.v
vlog -work work ../source/rtl/sfp_video_tx.v
vlog -work work ../source/rtl/video_async_fifo.v
vlog -work work tb_sfp50k_tx.v
vsim -c -lib work tb_sfp50k_tx
vcd file dbg50k.vcd
vcd add tb_sfp50k_tx/txd tb_sfp50k_tx/txk tb_sfp50k_tx/o_clk tb_sfp50k_tx/c_vs tb_sfp50k_tx/c_de
run 1.2ms
quit -f
