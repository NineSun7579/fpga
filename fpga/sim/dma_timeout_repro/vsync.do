onerror {quit -code 1 -force}
vlib work
vlog -sv ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v ../../source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v tb_vsync.sv
vsim -voptargs=+acc work.tb_vsync
run -all
quit -code 0 -force
