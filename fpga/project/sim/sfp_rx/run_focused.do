onerror {quit -code 1 -f}
if {![file exists focused_work]} {vlib focused_work}
vlog -sv -work focused_work ../../source/sfp/video_async_fifo.v ../../source/sfp/sfp_rx_cam_if.v ../../source/sfp/sfp_video_rx.v tb_sfp_rx_cam_if_empty.v tb_sfp_video_rx_ctrl.v
vsim -c -onfinish stop focused_work.tb_sfp_rx_cam_if_empty
run -all
if {[examine -radix decimal /tb_sfp_rx_cam_if_empty/errors] != 0} {quit -code 1 -f}
quit -sim
vsim -c -onfinish stop focused_work.tb_sfp_video_rx_ctrl
run -all
if {[examine -radix decimal /tb_sfp_video_rx_ctrl/errors] != 0} {quit -code 1 -f}
quit -code 0 -f
