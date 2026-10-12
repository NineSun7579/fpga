transcript on
if {[file exists work]} { vdel -all -lib work }
vlib work
vmap work work
set P "../../source"
set I "../../ipcore"
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
vlog -quiet "$V/GTP_GRS.v"
vlog -quiet "$P/ov5640/ovreg_axil_decode.v" "$P/ov5640/ov5640_reg.v"
vlog -quiet "$P/ov5640/ov5640_top.v" "$P/ov5640/ov5640/ov5640.v"
vlog -quiet "$P/ov5640/ov5640/cmos_capture.v" "$P/ov5640/ov5640/i2c_dir.v"
vlog -quiet "$P/ov5640/ov5640/ov5640_cdc.v" "$P/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v"
vlog -quiet "$P/ov5640/ov5640_ddr/ov5640_ddr.v" "$P/ov5640/ov5640_ddr/ov5640_ddr_w.v"
vlog -quiet "$P/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v" "$P/ov5640/ov5640_ddr/ov5640_ddr_w_en.v"
vlog -quiet "$I/ov5640_cdc_fifo/ov5640_cdc_fifo.v"
vlog -quiet "$I/ov5640_cdc_fifo/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_cdc_fifo.v"
vlog -quiet "$I/ov5640_cdc_fifo/rtl/ipm2l_fifo_v1_10_ov5640_cdc_fifo.v"
vlog -quiet "$I/ov5640_cdc_fifo/rtl/ipm2l_sdpram_v1_10_ov5640_cdc_fifo.v"
vlog -quiet "$I/ov5640_vhsync/ov5640_vhsync.v"
vlog -quiet "$I/ov5640_vhsync/rtl/ipm_distributed_fifo_ctr_v1_1_ov5640_vhsync.v"
vlog -quiet "$I/ov5640_vhsync/rtl/ipm_distributed_fifo_v1_4_ov5640_vhsync.v"
vlog -quiet "$I/ov5640_vhsync/rtl/ipm_distributed_sdpram_v1_3_ov5640_vhsync.v"
vlog -quiet "$V/GTP_DRM18K_E1.v" "$V/GTP_DRM9K_E1.v" "$V/GTP_DRM18K.v" "$V/GTP_DRM9K.v" "$V/GTP_DRM36K_E1.v"
vlog -quiet "$I/ov5640_ddr_fifo_DRM/ov5640_ddr_fifo_DRM.v"
vlog -quiet "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_ddr_fifo_DRM.v"
vlog -quiet "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_fifo_v1_10_ov5640_ddr_fifo_DRM.v"
vlog -quiet "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_sdpram_v1_10_ov5640_ddr_fifo_DRM.v"
vlog -quiet "$P/ov5640/pipe_cdc.v"
vlog -quiet "$I/ov5640_ddr_fifo/ov5640_ddr_fifo.v"
vlog -quiet "$I/ov5640_ddr_fifo/rtl/ipm_distributed_fifo_ctr_v1_1_ov5640_ddr_fifo.v"
vlog -quiet "$I/ov5640_ddr_fifo/rtl/ipm_distributed_fifo_v1_4_ov5640_ddr_fifo.v"
vlog -quiet "$I/ov5640_ddr_fifo/rtl/ipm_distributed_sdpram_v1_3_ov5640_ddr_fifo.v"
vlog -quiet ../../../sim/ov5640_tb/gtp_iodelay_stub.v
vlog -quiet ../../../sim/ov5640_tb/tb_dual_cam.v
vsim -c tb_dual_cam
run -all
quit -f
