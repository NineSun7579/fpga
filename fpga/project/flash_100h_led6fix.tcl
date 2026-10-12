cfg_scan_chain
cfg_assign_file -file C:/Users/NineSun/Desktop/ov56401/project/project_build/generate_bitstream/top.sbit -device_index 0
flash_erase -erase_type chip
flash_program -file C:/Users/NineSun/Desktop/ov56401/project/project_build/generate_bitstream/top.sbit -mode spi -spiaddr 0x0 -device_index 0
