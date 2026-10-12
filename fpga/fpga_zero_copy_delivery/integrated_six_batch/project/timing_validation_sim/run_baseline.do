onerror {quit -code 2}
vlib baseline_work
vlog -work baseline_work vendor_endpoint_stubs.v {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/sim_six_batch/pcie_fifo_baseline_modelsim.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/ov5640/axi_to_axi_lite.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/delivery/delivery_raw_letterbox.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/delivery/delivery_regs.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/delivery/delivery_rgb888_pack128.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/delivery/delivery_rgb_ddr.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/delivery/delivery_top_adapter.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/display/display_rgb565_pack128.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/display/display_thumbnail_ddr.v} {D:/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/integrated_six_batch/source/display/rgb565_display_decimator.v}
vlog -work baseline_work -sv six_batch_tb.sv
vsim -c -onfinish exit -voptargs=+acc baseline_work.six_batch_tb
run -all
quit -code 0
