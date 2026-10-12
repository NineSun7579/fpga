# Run from project/sim/motion: vsim -c -l cdc_console.log -do run_cdc.do
onerror {quit -code 1 -force}
# Dedicated library/log avoids other motion agents' simulation artifacts.
transcript file cdc_results.log
if {![file exists cdc_work]} {vlib cdc_work}
vlog -work cdc_work ../../source/motion/motion_result_cdc.v
vlog -sv -work cdc_work tb_motion_result_cdc.sv
vsim -onfinish stop -wlf cdc_wave.wlf cdc_work.tb_motion_result_cdc
run -all
if {[examine -radix binary /tb_motion_result_cdc/done] ne "111"} {quit -code 1 -force}
quit -code 0 -force
