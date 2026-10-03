onerror {quit -code 1 -f}
set SRC .
set LIB C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation
foreach {key value} {PA 23.8095 PB 23.8095 PO 16.0 SHIFT 0} {
    if {![info exists $key]} {set $key $value}
}
if {![file exists work]} {vlib work}
vlog -work work $LIB/GTP_IOCLKBUF.v $LIB/GTP_IOCLKDIV.v
vlog -work work $SRC/cmos_8_16bit.v $SRC/video_async_fifo.v $SRC/cam2_merge.v
vlog -sv -work work tb_merge_rows.sv
vsim -voptargs=+acc -gPA=$PA -gPB=$PB -gPO=$PO -gSHIFT=$SHIFT work.tb_merge_rows work.GRS_INST
run -all
quit -code 0 -f
