onerror {quit -code 1 -force}
vsim -onfinish stop -voptargs=+acc -gH=480 -gBLANK=12500 -gTAIL=256 work.tb_receiver +EXP5=6 +EXP6=6
run -all
quit -code 0 -force
