cfg_connect -ip 127.0.0.1 -port 65491
cfg_scan_chain
cfg_assign_file -file {D:/race/fpga/git/fpga/fpga/bitstream_sfp6_20260929/top.sbit} -device_index 0
cfg_program -device_index 0
cfg_disconnect
exit
