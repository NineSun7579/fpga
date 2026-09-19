if {[file exists work_cl]} { vdel -all -lib work_cl }
vlib work_cl
vmap work_cl work_cl
set I "../../ipcore"
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
vlog -quiet -work work_cl "$V/GTP_GRS.v"
vlog -quiet -work work_cl "$V/GTP_DRM18K_E1.v" "$V/GTP_DRM9K_E1.v" "$V/GTP_DRM18K.v" "$V/GTP_DRM9K.v" "$V/GTP_DRM36K_E1.v"
vlog -quiet -work work_cl "$I/ov5640_cdc_fifo/ov5640_cdc_fifo.v"
vlog -quiet -work work_cl "$I/ov5640_cdc_fifo/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_cdc_fifo.v"
vlog -quiet -work work_cl "$I/ov5640_cdc_fifo/rtl/ipm2l_fifo_v1_10_ov5640_cdc_fifo.v"
vlog -quiet -work work_cl "$I/ov5640_cdc_fifo/rtl/ipm2l_sdpram_v1_10_ov5640_cdc_fifo.v"
vlog -quiet -work work_cl ../../../sim/ov5640_tb/tb_cdc_lat.v
vsim -c -lib work_cl tb_cdc_lat
run -all
quit -f
