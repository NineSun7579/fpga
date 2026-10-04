onerror {quit -code 1}
if {[file exists work_boot]} {vdel -lib work_boot -all}
vlib work_boot
vmap work work_boot
vlog +define+TOP_BOOT_CLOCK_MOCKS input_clock_model.v
vlog -sv ../source/rtl/video_reset_sync.v ../source/rtl/video_mode_keys.v ../source/rtl/video_mode_switch.v ../source/rtl/hdmi_720p_capture.v ../source/rtl/ms7200_config.v ../source/rtl/hdmi_ddr_ov5640_top.v ../source/rtl/cam2_merge.v ../source/rtl/video_async_fifo.v ../source/rtl/sfp_video_tx.v ../source/rtl/cmos_8_16bit.v ../source/rtl/reg_config.v ../source/rtl/i2c_com.v ../source/rtl/power_on_delay.v ../source/rtl/ms7200_ctl.v ../source/rtl/iic_dri.v top_boot_mocks.v tb_diagnostic_boot.sv
vsim -t 1ps work.tb_diagnostic_boot
run -all
quit -code 0
