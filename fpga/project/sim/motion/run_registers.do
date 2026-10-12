onerror {quit -code 1 -force}
# Run from project/sim/motion; use a local mapping file.
if {![file exists modelsim.ini]} {vmap -c}
if {![file exists work_registers]} {vlib work_registers}
vmap work work_registers
set stage ../../motion_100h/source
vlog -work work $stage/motion/motion_register_bank.v $stage/preprocess/prep_regs.v $stage/ov5640/ovreg_axil_decode.v
vlog -sv -work work tb_motion_registers.sv
vsim -c work.tb_motion_registers
onbreak {quit -code 1 -force}
run -all
quit -code 0 -force
