onerror {quit -code 1 -force}
set simdir [pwd]
cd $simdir
set vendor C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation
set actual ../../../ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/cmos_8_16bit.v
if {![file exists work]} {vlib work}
if {![file exists modelsim.ini]} {vmap -c}
vmap -modelsimini modelsim.ini work work
vlog "$vendor/GTP_GRS.v" "$vendor/GTP_IOCLKBUF.v" "$vendor/GTP_IOCLKDIV.v"
vlog $actual
vlog -sv tb_cmos50k.sv
vsim -modelsimini modelsim.ini -t 1ps work.tb_cmos50k
run -all
quit -code 0 -force
