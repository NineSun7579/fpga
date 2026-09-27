onerror {quit -code 1 -force}
vlib work_throughput
set I "../../ipcore"
set V "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation"
vlog -work work_throughput "$V/GTP_GRS.v" "$V/GTP_DRM18K_E1.v" "$V/GTP_DRM9K_E1.v" "$V/GTP_DRM18K.v" "$V/GTP_DRM9K.v" "$V/GTP_DRM36K_E1.v"
vlog -work work_throughput "$I/ov5640_ddr_fifo_DRM/ov5640_ddr_fifo_DRM.v" "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_fifo_ctrl_v1_1_ov5640_ddr_fifo_DRM.v" "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_fifo_v1_10_ov5640_ddr_fifo_DRM.v" "$I/ov5640_ddr_fifo_DRM/rtl/ipm2l_sdpram_v1_10_ov5640_ddr_fifo_DRM.v"
vlog -work work_throughput "$I/ov5640_ddr_fifo/ov5640_ddr_fifo.v" "$I/ov5640_ddr_fifo/rtl/ipm_distributed_fifo_ctr_v1_1_ov5640_ddr_fifo.v" "$I/ov5640_ddr_fifo/rtl/ipm_distributed_fifo_v1_4_ov5640_ddr_fifo.v" "$I/ov5640_ddr_fifo/rtl/ipm_distributed_sdpram_v1_3_ov5640_ddr_fifo.v"
vlog -work work_throughput "$I/ddr_fifo16_w/ddr_fifo16_w.v" "$I/ddr_fifo16_w/rtl/ipm_distributed_fifo_ctr_v1_1_ddr_fifo16_w.v" "$I/ddr_fifo16_w/rtl/ipm_distributed_fifo_v1_4_ddr_fifo16_w.v" "$I/ddr_fifo16_w/rtl/ipm_distributed_sdpram_v1_3_ddr_fifo16_w.v"
vlog -work work_throughput -sv +define+VENDOR_FIFO+CREDIT_PORTS ../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v ../../source/ov5640/ov5640_ddr/ov5640_ddr.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v ../../source/axi_crossbar/ddr_w_arb.v tb_throughput.sv
vsim -voptargs=+acc work_throughput.tb_throughput -gGATED=1 +FRAMES=3
run -all
quit -code 0 -force
