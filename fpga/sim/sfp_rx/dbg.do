set MS C:/modeltech64_10.6e/win64
if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work ../../source/sfp/sfp_video_rx.v
vlog -work work C:/Users/NineSun/Desktop/ov56401/21_OV5640_SFP480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v
vlog -work work C:/Users/NineSun/Desktop/ov56401/21_OV5640_SFP480p_test/ov5640_sfp480p_test/source/rtl/video_async_fifo.v
vlog -work work tb_sfp_link.v
vsim -c -lib work tb_sfp_link
log -r /*
add list /tb_sfp_link/txd /tb_sfp_link/txk /tb_sfp_link/rxd /tb_sfp_link/rxk
add list /tb_sfp_link/u_rx/o_vs /tb_sfp_link/u_rx/o_de /tb_sfp_link/u_rx/wptr /tb_sfp_link/u_rx/rptr
run 60us
write format wave -window .main_pane.wave.interior.cs.body.pw.wf wave.do
quit -f
