if {[file exists work_ol]} { vdel -all -lib work_ol }
vlib work_ol
vmap work_ol work_ol
set I "../../ipcore"
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
vlog -quiet -work work_ol "$V/GTP_GRS.v"
vlog -quiet -work work_ol "$I/ov5640_ddr_fifo/ov5640_ddr_fifo.v"
vlog -quiet -work work_ol "$I/ov5640_ddr_fifo/rtl/ipm_distributed_fifo_ctr_v1_1_ov5640_ddr_fifo.v"
vlog -quiet -work work_ol "$I/ov5640_ddr_fifo/rtl/ipm_distributed_fifo_v1_4_ov5640_ddr_fifo.v"
vlog -quiet -work work_ol "$I/ov5640_ddr_fifo/rtl/ipm_distributed_sdpram_v1_3_ov5640_ddr_fifo.v"
vlog -quiet -work work_ol ../../../sim/ov5640_tb/tb_out_lat.v
vsim -c -lib work_ol tb_out_lat
run -all
quit -f
