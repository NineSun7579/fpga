cfg_gen_sfc -sbit C:/Users/NineSun/Desktop/ov56401/project/generate_bitstream/top.sbit
cfg_scan_chain
cfg_jtag_flash_scan_device -device_index 0
cfg_jtag_flash_assign_file -file C:/Users/NineSun/Desktop/ov56401/project/generate_bitstream/top.sfc -device_index 0
cfg_jtag_flash_erase -device_index 0
cfg_jtag_flash_program -device_index 0
cfg_jtag_flash_verify -device_index 0
