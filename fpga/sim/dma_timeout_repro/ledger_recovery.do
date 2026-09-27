onerror {quit -code 1 -force}
vlib work_ledger
vlog -sv -work work_ledger ../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v ../../source/axi_crossbar/ddr_w_arb.v tb_timeout_recovery.sv
vsim -voptargs=+acc work_ledger.tb_timeout_recovery
run -all
quit -code 0 -force
