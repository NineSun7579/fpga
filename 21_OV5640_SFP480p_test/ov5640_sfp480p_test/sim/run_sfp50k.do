# run_sfp50k.do -- 50K 发送链路仿真 (双摄 -> merge -> sfp_video_tx -> 光口字解码)
set SRC ../source/rtl
if {[file exists work]} { vdel -lib work -all }
vlib work
vlog -work work $SRC/cam2_merge.v
vlog -work work $SRC/sfp_video_tx.v
vlog -work work $SRC/video_async_fifo.v
vlog -work work tb_sfp50k_tx.v
vsim -c -lib work tb_sfp50k_tx
run -all
quit -f
