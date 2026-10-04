onerror {quit -code 1}
vlib work_input_pll
vmap work work_input_pll
vlog E:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_PLL_E3.v E:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_CLKBUFG.v E:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_GRS.v
vlog -sv ../source/rtl/video_reset_sync.v ../source/rtl/video_async_fifo.v ../source/rtl/hdmi_720p_capture.v tb_input_pll.sv
vsim -t 10fs work.tb_input_pll
run -all
quit -code 0
