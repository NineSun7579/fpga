onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate -divider -height 25 {Clock&Reset Ports}
add wave -noupdate /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/i_clk
add wave -noupdate /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/i_rstn
add wave -noupdate -divider -height 25 {Input Data Ports}
add wave -noupdate -radix hexadecimal /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/i_axi4s_data_tdata
add wave -noupdate  /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/i_axi4s_data_tlast
add wave -noupdate  /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/o_axi4s_data_tready
add wave -noupdate  /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/i_axi4s_data_tvalid
add wave -noupdate -divider -height 25 {Output Data Ports}
add wave -noupdate -radix hexadecimal /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/o_axi4s_data_tdata
add wave -noupdate  /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/o_axi4s_data_tlast
add wave -noupdate  /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/i_axi4s_data_tready
add wave -noupdate  /ipsxe_fir_onboard_top_tb/u_ipsxe_fir_onboard_top/u_FIR/o_axi4s_data_tvalid
TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 10} {15338254000 fs} 0}
configure wave -namecolwidth 150
configure wave -valuecolwidth 100
configure wave -justifyvalue left
configure wave -signalnamewidth 1
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits ns
update
WaveRestoreZoom {0 ps} {1140304578 ps}
