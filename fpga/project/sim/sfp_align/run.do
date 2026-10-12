onerror {quit -code 1 -force}
vlib work
vlog -sv hsst_sfp_stub.v ../../source/sfp/sfp_rx_link.v ../../source/sfp/sfp_video_rx.v tb_sfp_align.v
quit -code 0 -force
