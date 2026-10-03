onerror {quit -code 1}
onbreak {quit -code 1}
vlib work
vlog -sv ../../source/preprocess/prep_regs.v tb_sfp_diag.v
vsim -c work.tb_sfp_diag
run -all
quit -code 0
