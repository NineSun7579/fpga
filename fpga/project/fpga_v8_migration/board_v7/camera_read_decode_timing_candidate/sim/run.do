onerror {quit -code 1 -force}
vlib work
vlog -sv ov5640_reg_reference.v ov5640_reg_candidate.v tb_camera_read_decode.sv
vsim -voptargs=+acc work.tb_camera_read_decode
onbreak {quit -code 1 -force}
run -all
quit -code 0 -force
