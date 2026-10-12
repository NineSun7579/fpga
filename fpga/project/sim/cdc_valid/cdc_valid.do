onerror {quit -code 1 -force}
vlib work_cdcv
set I "../../ipcore"
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
vlog -work work_cdcv "$V/GTP_GRS.v" "$V/GTP_DRM18K_E1.v"
vlog -work work_cdcv "$I/ov5640_cdc_fifo/ov5640_cdc_fifo.v" "$I/ov5640_cdc_fifo/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_cdc_fifo.v" "$I/ov5640_cdc_fifo/rtl/ipm2l_fifo_v1_10_ov5640_cdc_fifo.v" "$I/ov5640_cdc_fifo/rtl/ipm2l_sdpram_v1_10_ov5640_cdc_fifo.v"
vlog -work work_cdcv -sv ../../source/ov5640/ov5640/ov5640_cdc.v ../../source/ov5640/cam_fir3.v tb_cdc_valid.sv
vsim -voptargs=+acc work_cdcv.tb_cdc_valid
run -all
quit -code 0 -force
