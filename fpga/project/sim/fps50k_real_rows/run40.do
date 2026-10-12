onerror {quit -code 1 -f}
set LIB C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation
if {![file exists work]} {vlib work}
vlog -work work $LIB/GTP_IOCLKBUF.v $LIB/GTP_IOCLKDIV.v
vlog -work work cmos_8_16bit.v video_async_fifo.v cam2_merge.v
vlog -sv -work work tb_merge_rows.sv
vsim -voptargs=+acc -gPA=23.8095 -gPB=23.8095 -gPO=16.0 -gSHIFT=5000 -gVTS=520 work.tb_merge_rows work.GRS_INST
run -all
quit -code 0 -f
