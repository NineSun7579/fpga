onerror {quit -code 1 -force}
onbreak {
    if {[examine -radix unsigned /tb_six_motion/success] != 1} {
        quit -code 1 -force
    }
    quit -code 0 -force
}
set here [pwd]
set extras {}
if {[info exists env(SIX_MOTION_FAULT)] && $env(SIX_MOTION_FAULT) == 1} {
    set extras {+INJECT_FAULT}
    transcript file six_motion_fault.log
} else {
    transcript file six_motion_results.log
}
# Private mapping and library: never modify the shared modelsim.ini/work.
set ini [file join $here six_motion_modelsim.ini]
if {![file exists $ini]} {
    file copy [file join $env(MODEL_TECH) .. modelsim.ini] $ini
    file attributes $ini -readonly 0
}
set env(MODELSIM) $ini
if {![file exists six_motion_work]} {vlib six_motion_work}
vmap -modelsimini $ini six_motion_work six_motion_work
vlog -modelsimini $ini -work six_motion_work -sv \
    ../../motion_100h/source/motion/block_motion_detector.v \
    ../../motion_100h/source/motion/motion_stream_adapter.v \
    ../../motion_100h/source/motion/motion_register_bank.v tb_six_motion.sv
eval vsim -modelsimini $ini -wlf six_motion.wlf -c six_motion_work.tb_six_motion $extras
onfinish stop
run -all
if {[examine -radix unsigned /tb_six_motion/success] != 1} {quit -code 1 -force}
quit -code 0 -force
