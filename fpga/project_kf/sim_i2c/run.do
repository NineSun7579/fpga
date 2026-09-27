transcript on
if {[file exists work]} { vdel -all -lib work }
vlib work
vmap work work
vlog -work work "C:/Users/NineSun/Desktop/ov56401/project/source/ov5640/ov5640/i2c_dir.v" "C:/Users/NineSun/Desktop/ov56401/project/source/ov5640/ov5640/ov5640_i2c_rgb565_cfg.v" "C:/Users/NineSun/Desktop/ov56401/project/project/sim_i2c/tb_ov5640_i2c.v"
vsim -c -lib work tb_ov5640_i2c -do "run -all; quit -f" -l sim_i2c.log
