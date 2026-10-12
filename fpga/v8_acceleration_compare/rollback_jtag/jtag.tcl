cfg_scan_chain
cfg_set_cable_property -index 0 -freq 1MHz
cfg_assign_file -file {D:/race/fpga/git/fpga/fpga/bitstream_cam5_fix_20261008/top.sbit} -device_index 0
cfg_program -device_index 0
