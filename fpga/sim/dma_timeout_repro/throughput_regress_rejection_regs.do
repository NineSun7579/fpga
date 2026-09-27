onerror {quit -code 1 -force}
vlib work_rejection_regs
vlog -work work_rejection_regs -sv ../../source/ov5640/ov5640_reg.v ../../source/ov5640/ov5640_top.v tb_rejection_regs.sv
vsim work_rejection_regs.tb_rejection_regs
run -all
quit -code 0 -force
