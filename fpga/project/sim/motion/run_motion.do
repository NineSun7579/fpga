onerror {quit -code 1 -force}
onbreak {
    if {[examine -radix unsigned /tb_block_motion_detector/success] != 1} {
        quit -code 1 -force
    }
    quit -code 0 -force
}
set here [pwd]
transcript file motion_results.log
if {![file exists modelsim.ini]} {vmap -c}
set env(MODELSIM) [file join $here modelsim.ini]
if {![file exists work]} {vlib work}
vmap work work
vlog -sv ../../source/motion/block_motion_detector.v tb_block_motion_detector.sv
vsim -c -voptargs=+acc work.tb_block_motion_detector
onfinish stop
run -all
if {[examine -radix unsigned /tb_block_motion_detector/success] != 1} {
    quit -code 1 -force
}
quit -code 0 -force
