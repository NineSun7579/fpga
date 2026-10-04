onerror {quit -code 1}
if {[file exists work_camera]} {vdel -lib work_camera -all}
vlib work_camera
vmap work work_camera
vlog -sv ../source/rtl/power_on_delay.v tb_camera_disable.sv
vsim -t 1ps work.tb_camera_disable
run -all
quit -code 0
