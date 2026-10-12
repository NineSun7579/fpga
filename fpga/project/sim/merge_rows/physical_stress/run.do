onerror {quit -code 1 -f}
set SRC ../../../../ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl
set LIB C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation
foreach {key value} {EXTRA 0 MODE 0 PA 11.9045 PB 11.900 PO 16.0 SHIFT 0} {
    if {![info exists $key]} {set $key $value}
}
if {[file exists work]} {vdel -lib work -all}
vlib work
vlog -work work $LIB/GTP_IOCLKBUF.v $LIB/GTP_IOCLKDIV.v
if {![info exists MERGE]} {set MERGE $SRC/cam2_merge.v}
vlog -work work $SRC/cmos_8_16bit.v $SRC/video_async_fifo.v $MERGE
vlog -sv -work work tb_merge_rows.sv
vsim -voptargs=+acc -gEXTRA=$EXTRA -gMODE=$MODE -gPA=$PA -gPB=$PB -gPO=$PO -gSHIFT=$SHIFT work.tb_merge_rows work.GRS_INST
run -all
quit -f
