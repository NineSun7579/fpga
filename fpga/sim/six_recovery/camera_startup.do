onerror {quit -code 1 -force}
vlib work_startup
vlog -work work_startup -sv +incdir+. ../../source/ov5640/ov5640/ov5640.v ../../source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v ../../source/ov5640/ov5640/i2c_dir.v ../../source/ov5640/ov5640/cmos_capture.v cdc_idle_stub.sv tb_camera_startup.sv
vsim -voptargs=+acc work_startup.tb_camera_startup
run -all
quit -code 0 -force
