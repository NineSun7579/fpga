onerror {quit -code 1 -force}
vlib work
if {![info exists dma_source]} {set dma_source ../../source/axi_dma/axi_dma_write.v}
vlog -sv $dma_source ../../source/axi_dma/stream_pipe.v ../../source/axi_crossbar/ddr_w_arb.v tb_timeout.sv
vsim -voptargs=+acc work.tb_timeout
run -all
quit -code 0 -force
