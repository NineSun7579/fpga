file delete -force work
vlib  work
vmap  work work
vlog -incr \
C:/pango/PDS_2022.2-SP6.4/ip/system_ip/ipsxe_fir/ipsxe_fir_eval/ipsxe_fir/../../../../../arch/vendor/pango/verilog/simulation/GTP_APM_E2.v \
C:/pango/PDS_2022.2-SP6.4/ip/system_ip/ipsxe_fir/ipsxe_fir_eval/ipsxe_fir/../../../../../arch/vendor/pango/verilog/simulation/GTP_GRS.v \
-f ./ipsxe_fir_onboard_top.f -l vlog.log
vsim -novopt work.ipsxe_fir_onboard_top_tb -l vsim.log
do ipsxe_fir_onboard_top_wave.do
run -all
