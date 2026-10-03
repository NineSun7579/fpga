if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work ../source/rtl/cam2_merge.v
vlog -work work ../source/rtl/sfp_video_tx.v
vlog -work work ../source/rtl/video_async_fifo.v
vlog -work work tb_sfp50k_tx.v
vsim -c -lib work tb_sfp50k_tx
vcd file dbg50kb.vcd
vcd add tb_sfp50k_tx/rst_n tb_sfp50k_tx/link_ready tb_sfp50k_tx/u_tx/fab_rst_n tb_sfp50k_tx/u_tx/tx_go tb_sfp50k_tx/u_tx/fifo_empty tb_sfp50k_tx/u_tx/fifo_rdata tb_sfp50k_tx/u_tx/pix_pend
run 1.2ms
quit -f
