onerror {quit -code 1 -force}
vlib work_rejection_diag
vlog -work work_rejection_diag -sv ../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v ../../source/ov5640/ov5640_ddr/ov5640_ddr.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v fifo_models.sv tb_rejection_diag.sv
vsim -voptargs=+acc work_rejection_diag.tb_rejection_diag
run -all
quit -code 0 -force
