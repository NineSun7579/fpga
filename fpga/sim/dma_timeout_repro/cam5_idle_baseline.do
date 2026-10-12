onerror {quit -code 1 -force}
vlib work_cam5_idle_baseline
vlog -work work_cam5_idle_baseline -sv ../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v cam5_idle_recovery_before.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v fifo_models.sv tb_cam5_idle_recovery.sv
vsim -voptargs=+acc work_cam5_idle_baseline.tb_cam5_idle_recovery
run -all
quit -code 0 -force
