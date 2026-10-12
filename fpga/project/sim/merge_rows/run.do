onerror {quit -code 1 -f}
set SRC ../../../ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl
set LIB C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation
if {[file exists work]} {vdel -lib work -all}
vlib work
vlog -work work $LIB/GTP_IOCLKBUF.v $LIB/GTP_IOCLKDIV.v
if {![info exists MERGE]} {set MERGE $SRC/cam2_merge.v}
if {![info exists EXTRA]} {set EXTRA 0}
if {![info exists PA]} {set PA 47.619}
if {![info exists PB]} {set PB 47.600}
if {![info exists PO]} {set PO 16.0}
if {![info exists VTS]} {set VTS 705}
vlog -work work $SRC/cmos_8_16bit.v $SRC/video_async_fifo.v $MERGE
vlog -sv -work work tb_merge_rows.sv
vsim -voptargs=+acc -gEXTRA=$EXTRA -gPA=$PA -gPB=$PB -gPO=$PO -gVTS=$VTS work.tb_merge_rows work.GRS_INST
run -all
quit -f
