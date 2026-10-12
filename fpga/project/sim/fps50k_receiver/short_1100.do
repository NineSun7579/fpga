onerror {quit -code 1 -force}
vsim -onfinish stop -voptargs=+acc -gH=2 -gBLANK=8 -gTAIL=1100 work.tb_receiver +EXP5=3 +EXP6=3
run -all
quit -code 0 -force
