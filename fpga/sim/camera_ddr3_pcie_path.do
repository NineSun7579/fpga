transcript on
if {[file exists work]} { vdel -all -lib work }
vlib work
vmap work work
vlog -work work ../rtl/ov5640_dri/cmos_capture_data.v
vlog -work work camera_ddr3_pcie_path_tb.v
vsim -voptargs=+acc work.camera_ddr3_pcie_path_tb
add wave -r sim:/camera_ddr3_pcie_path_tb/*
add wave -r sim:/camera_ddr3_pcie_path_tb/u_capture/*
run -all
