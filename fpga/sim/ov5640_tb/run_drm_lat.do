if {[file exists work_lat]} { vdel -all -lib work_lat }
vlib work_lat
vmap work_lat work_lat
set I "../../ipcore"
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
vlog -quiet -work work_lat "$V/GTP_GRS.v"
vlog -quiet -work work_lat "$V/GTP_DRM18K_E1.v" "$V/GTP_DRM9K_E1.v" "$V/GTP_DRM18K.v" "$V/GTP_DRM9K.v" "$V/GTP_DRM36K_E1.v"
vlog -quiet -work work_lat "$I/ov5640_ddr_fifo_DRM/ov5640_ddr_fifo_DRM.v"
vlog -quiet -work work_lat "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_ddr_fifo_DRM.v"
vlog -quiet -work work_lat "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_fifo_v1_10_ov5640_ddr_fifo_DRM.v"
vlog -quiet -work work_lat "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_sdpram_v1_10_ov5640_ddr_fifo_DRM.v"
vlog -quiet -work work_lat ../../../sim/ov5640_tb/tb_drm_lat.v
vsim -c -lib work_lat tb_drm_lat
run -all
quit -f
