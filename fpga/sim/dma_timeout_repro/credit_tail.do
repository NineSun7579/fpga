onerror {quit -code 1 -force}
vlib work_credit_tail
vlog -work work_credit_tail -sv ../../source/axi_dma/axi_dma_write.v ../../source/axi_dma/stream_pipe.v tb_credit_tail.sv
vsim -voptargs=+acc work_credit_tail.tb_credit_tail
run -all
quit -code 0 -force
