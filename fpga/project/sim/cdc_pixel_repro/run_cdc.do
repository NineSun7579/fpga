onerror {quit -code 1 -force}
vlib work_cdc
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
set I "../../ipcore/ov5640_cdc_fifo"
vlog -work work_cdc "$V/GTP_GRS.v" "$V/GTP_DRM18K_E1.v" "$V/GTP_DRM9K_E1.v" "$V/GTP_DRM18K.v" "$V/GTP_DRM9K.v" "$V/GTP_DRM36K_E1.v"
vlog -work work_cdc "$I/ov5640_cdc_fifo.v" "$I/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_cdc_fifo.v" "$I/rtl/ipm2l_fifo_v1_10_ov5640_cdc_fifo.v" "$I/rtl/ipm2l_sdpram_v1_10_ov5640_cdc_fifo.v"
vlog -work work_cdc -sv ../../source/ov5640/ov5640/ov5640_cdc.v tb_cdc_pixels.sv
vsim -voptargs=+acc work_cdc.tb_cdc_pixels
run -all
quit -code 0 -force
