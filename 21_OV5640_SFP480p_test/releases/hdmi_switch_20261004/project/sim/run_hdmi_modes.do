onerror {quit -code 1}
if {[file exists work_hdmi]} {vdel -lib work_hdmi -all}
vlib work_hdmi
vmap work work_hdmi
vlog input_clock_model.v
vlog -sv ../source/rtl/video_reset_sync.v ../source/rtl/video_mode_keys.v ../source/rtl/video_mode_switch.v ../source/rtl/hdmi_720p_capture.v ../source/rtl/video_async_fifo.v ../source/rtl/sfp_video_tx.v ../../receiver/sfp/sfp_video_rx.v tb_hdmi_modes.sv
vsim -t 1ps work.tb_hdmi_modes
run -all
quit -code 0
