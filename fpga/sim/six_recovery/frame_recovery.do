onerror {quit -code 1 -force}
vlib work_frame
vlog -work work_frame -sv ../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v ../../source/ov5640/ov5640_ddr/ov5640_ddr.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v ../dma_timeout_repro/fifo_models.sv ../dma_timeout_repro/tb_frame_recovery.sv
vsim -voptargs=+acc work_frame.tb_frame_recovery
run -all
quit -code 0 -force
