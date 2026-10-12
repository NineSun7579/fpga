transcript on
catch {vdel -all -lib work}
catch {vdel -all -lib work_registers}
vlib work
vlog -sv ../../source/ov5640/cam34_downsample_2x2.v tb_cam34_downsample.sv
vsim -c work.tb_cam34_downsample
run -all
quit -f
