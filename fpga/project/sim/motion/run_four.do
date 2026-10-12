onerror {quit -code 1 -force}
onbreak {
    if {[examine -radix unsigned /tb_four_motion/success] != 1} {
        quit -code 1 -force
    }
    quit -code 0 -force
}
set here [pwd]
set extras {}
if {[info exists env(FOUR_MOTION_FAULT)] && $env(FOUR_MOTION_FAULT) == 1} {
    set extras {+INJECT_FAULT}
    transcript file four_motion_fault.log
} else {
    transcript file four_motion_results.log
}
# Distinct private mapping/library: safe alongside six-motion and PDS sessions.
set ini [file join $here four_motion_modelsim.ini]
if {![file exists $ini]} {
    file copy [file join $env(MODEL_TECH) .. modelsim.ini] $ini
    file attributes $ini -readonly 0
}
set env(MODELSIM) $ini
if {![file exists four_motion_work]} {vlib four_motion_work}
vmap -modelsimini $ini four_motion_work four_motion_work
vlog -modelsimini $ini -work four_motion_work -sv \
    ../../motion_100h/source/motion/block_motion_detector.v \
    ../../motion_100h/source/motion/motion_stream_adapter.v \
    ../../motion_100h/source/motion/motion_register_bank.v tb_four_motion.sv
eval vsim -modelsimini $ini -wlf four_motion.wlf -c four_motion_work.tb_four_motion $extras
onfinish stop
run -all
if {[examine -radix unsigned /tb_four_motion/success] != 1} {quit -code 1 -force}
quit -code 0 -force
