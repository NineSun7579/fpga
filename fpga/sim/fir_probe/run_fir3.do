file delete -force work3
vlib  work3
vmap  work3 work3
vlog -work work3 ../../project/source/ov5640/cam_fir3.v tb_cam_fir3.v -l vlog3.log
vsim -novopt work3.tb_cam_fir3 -l vsim3.log
run -all
quit -f
