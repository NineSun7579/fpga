cfg_scan_chain
cfg_set_cable_property -index 0 -freq 1MHz
cfg_jtag_flash_scan_device -device_index 0
cfg_jtag_flash_assign_file -file C:/Users/NineSun/Desktop/ov56401/project/bitstream_six_recovery_20261002_192245/top.sbit -device_index 0
cfg_jtag_flash_erase -device_index 0
cfg_jtag_flash_program -device_index 0
cfg_jtag_flash_verify -device_index 0
