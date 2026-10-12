transcript on
if {[file exists work]} { vdel -all -lib work }
vlib work
vmap work ./work
vlog -quiet -work work ../../project/source/ov5640/cam_sharpen.v
vlog -quiet -work work tb_cam_sharpen.v
vsim -c -work work tb_cam_sharpen
run -all
quit -f
