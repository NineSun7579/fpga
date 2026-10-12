file delete -force work
vlib  work
vmap  work work
vlog -incr +define+IPSXE_FIR_SPEEDUP_SIM \
C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_APM_E2.v \
C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_GRS.v \
../../project/project/ipcore/FIR/FIR.v \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_core_v1_2_FIR.v \
C:/pango/PDS_2022.2-SP6.4/ip/system_ip/ipsxe_fir/ipsxe_fir_eval/ipsxe_fir/sim_lib/modelsim/ipsxe_fir_core_v1_2_simvpAll.vp \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_data_pipeline/ipsxe_fir_distributed_shiftregister.v \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_data_pipeline/ipsxe_fir_distributed_sdpram.v \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_data_pipeline/ipsxe_fir_data_pipeline.v \
../../project/project/ipcore/FIR/example_design/rtl/ipsxe_fir_cross_sync.v \
tb_fir_probe.v \
-l vlog.log
vsim -novopt work.tb_fir_probe -l vsim.log -voptargs=+acc
run -all
quit -f
