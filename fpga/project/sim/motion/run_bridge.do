onerror {quit -code 1 -force}
onbreak {
    if {[examine -radix unsigned /tb_motion_axi_bridge/success] != 1} {
        quit -code 1 -force
    }
    quit -code 0 -force
}
# Invoke from project/sim/motion: vsim -c -do run_bridge.do
# ModelSim's info script resolves an internal Tcl script, so use launch cwd.
set here [pwd]
transcript file bridge_results.log
if {![file exists bridge_modelsim.ini]} {
    file copy [file join $env(MODEL_TECH) .. modelsim.ini] bridge_modelsim.ini
}
set env(MODELSIM) [file join $here bridge_modelsim.ini]
if {![file exists bridge_work]} {vlib bridge_work}
vmap bridge_work bridge_work
set stage [file normalize [file join $here ../../motion_100h/source]]
vlog -work bridge_work -sv \
    [file join $stage ov5640/axi_to_axi_lite.v] \
    [file join $stage ov5640/ovreg_axil_decode.v] \
    [file join $stage motion/motion_register_bank.v] \
    [file join $stage preprocess/prep_regs.v] \
    [file join $here tb_motion_axi_bridge.sv]
vsim -c -voptargs=+acc bridge_work.tb_motion_axi_bridge
onfinish stop
run -all
if {[examine -radix unsigned /tb_motion_axi_bridge/success] != 1} {
    quit -code 1 -force
}
quit -code 0 -force
