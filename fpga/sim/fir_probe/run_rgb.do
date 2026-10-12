file delete -force work_rgb
vlib  work_rgb
vmap  work_rgb work_rgb
vlog -incr +define+IPSXE_FIR_SPEEDUP_SIM -work work_rgb \
C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_APM_E2.v \
C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_GRS.v \
../../project/project/ipcore/FIR/FIR.v \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_core_v1_2_FIR.v \
C:/pango/PDS_2022.2-SP6.4/ip/system_ip/ipsxe_fir/ipsxe_fir_eval/ipsxe_fir/sim_lib/modelsim/ipsxe_fir_core_v1_2_simvpAll.vp \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_data_pipeline/ipsxe_fir_distributed_shiftregister.v \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_data_pipeline/ipsxe_fir_distributed_sdpram.v \
../../project/project/ipcore/FIR/rtl/ipsxe_fir_data_pipeline/ipsxe_fir_data_pipeline.v \
tb_fir_rgb.v \
-l vlog_rgb.log
vsim -novopt work_rgb.tb_fir_rgb -l vsim_rgb.log
run -all
quit -f
