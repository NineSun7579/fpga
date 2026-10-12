onerror {quit -f -code 1}
vsim -onfinish stop -gCASE_ID=0 -gSEED=12345 work.tb_fpga_v8_ddr_write_arbiter +TRACE=trace.csv
run -all
quit -f -code 0
