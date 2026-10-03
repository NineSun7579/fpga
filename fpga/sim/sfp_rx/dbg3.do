if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work ../../source/sfp/sfp_video_rx.v
vlog -work work C:/Users/NineSun/Desktop/ov56401/21_OV5640_SFP480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v
vlog -work work C:/Users/NineSun/Desktop/ov56401/21_OV5640_SFP480p_test/ov5640_sfp480p_test/source/rtl/video_async_fifo.v
vlog -work work tb_sfp_link.v
vsim -c -lib work tb_sfp_link
vcd file dbg3.vcd
vcd add tb_sfp_link/o_vs tb_sfp_link/o_de tb_sfp_link/rxk tb_sfp_link/txk tb_sfp_link/u_tx/u_tx/u_fifo/wr_clk tb_sfp_link/u_tx/fifo_empty
run 3ms
quit -f
