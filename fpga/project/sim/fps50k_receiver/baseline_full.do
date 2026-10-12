onerror {quit -code 1 -force}
vsim -onfinish stop -voptargs=+acc -gH=480 -gBLANK=8 -gTAIL=256 work.tb_receiver +EXP5=6 +EXP6=3
run -all
quit -code 0 -force
