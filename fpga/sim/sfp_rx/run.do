# run.do -- tb_sfp_link 回归 (ModelSim)
# 用法: cd project/sim/sfp_rx && vsim -c -do run.do
set MS C:/modeltech64_10.6e/win64

if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work ../../source/sfp/sfp_video_rx.v
vlog -work work C:/Users/NineSun/Desktop/ov56401/21_OV5640_SFP480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v
vlog -work work C:/Users/NineSun/Desktop/ov56401/21_OV5640_SFP480p_test/ov5640_sfp480p_test/source/rtl/video_async_fifo.v
vlog -work work tb_sfp_link.v
vsim -c -lib work tb_sfp_link
run -all
quit -f
