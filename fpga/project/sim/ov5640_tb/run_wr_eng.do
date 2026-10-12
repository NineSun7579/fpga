if {[file exists work_we]} { vdel -all -lib work_we }
vlib work_we
vmap work_we work_we
set P "../../source"
vlog -quiet -work work_we "$P/axi_dma/stream_pipe.v"
vlog -quiet -work work_we "$P/axi_dma/axi_dma_write.v"
vlog -quiet -work work_we ../../../sim/ov5640_tb/tb_wr_eng.v
vsim -c -lib work_we tb_wr_eng
run -all
quit -f
