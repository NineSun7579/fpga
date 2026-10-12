onerror {quit -code 1 -force}
onbreak {quit -code 1 -force}
if {![file isdirectory adapter_work]} {vlib adapter_work}
vmap adapter_work adapter_work
vlog -work adapter_work ../../motion_100h/source/motion/block_motion_detector.v ../../motion_100h/source/motion/motion_stream_adapter.v tb_motion_stream_adapter.sv
vsim -c -lib adapter_work tb_motion_stream_adapter
run -all
quit -code 0 -force
