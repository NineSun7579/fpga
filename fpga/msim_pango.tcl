# ----------------------------------------
# Create compilation libraries
vlib usim
vmap usim "C:/Users/NineSun/Desktop/ov56401/project/usim"
vlib vsim
vmap vsim "C:/Users/NineSun/Desktop/ov56401/project/vsim"
vlib adc
vmap adc "C:/Users/NineSun/Desktop/ov56401/project/adc"
vlib adc_e2
vmap adc_e2 "C:/Users/NineSun/Desktop/ov56401/project/adc_e2"
vlib ddc_e2
vmap ddc_e2 "C:/Users/NineSun/Desktop/ov56401/project/ddc_e2"
vlib ddrc
vmap ddrc "C:/Users/NineSun/Desktop/ov56401/project/ddrc"
vlib ddrphy
vmap ddrphy "C:/Users/NineSun/Desktop/ov56401/project/ddrphy"
vlib dll_e2
vmap dll_e2 "C:/Users/NineSun/Desktop/ov56401/project/dll_e2"
vlib hsst
vmap hsst "C:/Users/NineSun/Desktop/ov56401/project/hsst"
vlib hsst_e2
vmap hsst_e2 "C:/Users/NineSun/Desktop/ov56401/project/hsst_e2"
vlib hssthp_bufds
vmap hssthp_bufds "C:/Users/NineSun/Desktop/ov56401/project/hssthp_bufds"
vlib hssthp_hpll
vmap hssthp_hpll "C:/Users/NineSun/Desktop/ov56401/project/hssthp_hpll"
vlib hssthp_lane
vmap hssthp_lane "C:/Users/NineSun/Desktop/ov56401/project/hssthp_lane"
vlib hsstlp_lane
vmap hsstlp_lane "C:/Users/NineSun/Desktop/ov56401/project/hsstlp_lane"
vlib hsstlp_pll
vmap hsstlp_pll "C:/Users/NineSun/Desktop/ov56401/project/hsstlp_pll"
vlib iolhp_fifo
vmap iolhp_fifo "C:/Users/NineSun/Desktop/ov56401/project/iolhp_fifo"
vlib iolhr_dft
vmap iolhr_dft "C:/Users/NineSun/Desktop/ov56401/project/iolhr_dft"
vlib ipal_e1
vmap ipal_e1 "C:/Users/NineSun/Desktop/ov56401/project/ipal_e1"
vlib ipal_e2
vmap ipal_e2 "C:/Users/NineSun/Desktop/ov56401/project/ipal_e2"
vlib iserdes_e1
vmap iserdes_e1 "C:/Users/NineSun/Desktop/ov56401/project/iserdes_e1"
vlib iserdes_e2
vmap iserdes_e2 "C:/Users/NineSun/Desktop/ov56401/project/iserdes_e2"
vlib iserdes_fifo
vmap iserdes_fifo "C:/Users/NineSun/Desktop/ov56401/project/iserdes_fifo"
vlib oserdes_e1
vmap oserdes_e1 "C:/Users/NineSun/Desktop/ov56401/project/oserdes_e1"
vlib oserdes_e2
vmap oserdes_e2 "C:/Users/NineSun/Desktop/ov56401/project/oserdes_e2"
vlib oserdes_fifo
vmap oserdes_fifo "C:/Users/NineSun/Desktop/ov56401/project/oserdes_fifo"
vlib pciegen2
vmap pciegen2 "C:/Users/NineSun/Desktop/ov56401/project/pciegen2"
vlib pciegen3
vmap pciegen3 "C:/Users/NineSun/Desktop/ov56401/project/pciegen3"


#compile basic library
vlog -incr "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/*.v" -work usim
vlog -incr "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/modelsim10.2c/*.vp" -work usim


#compile basic library
vlog -incr "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/bsim/*.v" -work vsim
vlog -incr "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/bsim/modelsim10.2c/*.vp" -work vsim


#compile common library
cd "C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/modelsim10.2c"
vmap adc "C:/Users/NineSun/Desktop/ov56401/project/adc"
vlog -incr -f ./filelist_adc_gtp.f -work adc
vmap adc_e2 "C:/Users/NineSun/Desktop/ov56401/project/adc_e2"
vlog -incr -f ./filelist_adc_e2_gtp.f -work adc_e2
vmap ddc_e2 "C:/Users/NineSun/Desktop/ov56401/project/ddc_e2"
vlog -incr -f ./filelist_ddc_e2_gtp.f -work ddc_e2
vmap ddrc "C:/Users/NineSun/Desktop/ov56401/project/ddrc"
vlog -incr -f ./filelist_ddrc_gtp.f -work ddrc -sv -mfcu
vmap ddrphy "C:/Users/NineSun/Desktop/ov56401/project/ddrphy"
vlog -incr -f ./filelist_ddrphy_gtp.f -work ddrphy
vmap dll_e2 "C:/Users/NineSun/Desktop/ov56401/project/dll_e2"
vlog -incr -f ./filelist_dll_e2_gtp.f -work dll_e2
vmap hsst "C:/Users/NineSun/Desktop/ov56401/project/hsst"
vlog -incr -f ./filelist_hsst_gtp.f -work hsst
vmap hsst_e2 "C:/Users/NineSun/Desktop/ov56401/project/hsst_e2"
vlog -incr -f ./filelist_hsst_e2_gtp.f -work hsst_e2
vmap hssthp_bufds "C:/Users/NineSun/Desktop/ov56401/project/hssthp_bufds"
vlog -incr -f ./filelist_hssthp_bufds_gtp.f -work hssthp_bufds
vmap hssthp_hpll "C:/Users/NineSun/Desktop/ov56401/project/hssthp_hpll"
vlog -incr -f ./filelist_hssthp_hpll_gtp.f -work hssthp_hpll
vmap hssthp_lane "C:/Users/NineSun/Desktop/ov56401/project/hssthp_lane"
vlog -incr -f ./filelist_hssthp_lane_gtp.f -work hssthp_lane
vmap hsstlp_lane "C:/Users/NineSun/Desktop/ov56401/project/hsstlp_lane"
vlog -incr -f ./filelist_hsstlp_lane_gtp.f -work hsstlp_lane
vmap hsstlp_pll "C:/Users/NineSun/Desktop/ov56401/project/hsstlp_pll"
vlog -incr -f ./filelist_hsstlp_pll_gtp.f -work hsstlp_pll
vmap iolhp_fifo "C:/Users/NineSun/Desktop/ov56401/project/iolhp_fifo"
vlog -incr -f ./filelist_iolhp_fifo_gtp.f -work iolhp_fifo
vmap iolhr_dft "C:/Users/NineSun/Desktop/ov56401/project/iolhr_dft"
vlog -incr -f ./filelist_iolhr_dft_gtp.f -work iolhr_dft
vmap ipal_e1 "C:/Users/NineSun/Desktop/ov56401/project/ipal_e1"
vlog -incr -f ./filelist_ipal_e1_gtp.f -work ipal_e1
vmap ipal_e2 "C:/Users/NineSun/Desktop/ov56401/project/ipal_e2"
vlog -incr -f ./filelist_ipal_e2_gtp.f -work ipal_e2
vmap iserdes_e1 "C:/Users/NineSun/Desktop/ov56401/project/iserdes_e1"
vlog -incr -f ./filelist_iserdes_e1_gtp.f -work iserdes_e1
vmap iserdes_e2 "C:/Users/NineSun/Desktop/ov56401/project/iserdes_e2"
vlog -incr -f ./filelist_iserdes_e2_gtp.f -work iserdes_e2
vmap iserdes_fifo "C:/Users/NineSun/Desktop/ov56401/project/iserdes_fifo"
vlog -incr -f ./filelist_iserdes_fifo_gtp.f -work iserdes_fifo
vmap oserdes_e1 "C:/Users/NineSun/Desktop/ov56401/project/oserdes_e1"
vlog -incr -f ./filelist_oserdes_e1_gtp.f -work oserdes_e1
vmap oserdes_e2 "C:/Users/NineSun/Desktop/ov56401/project/oserdes_e2"
vlog -incr -f ./filelist_oserdes_e2_gtp.f -work oserdes_e2
vmap oserdes_fifo "C:/Users/NineSun/Desktop/ov56401/project/oserdes_fifo"
vlog -incr -f ./filelist_oserdes_fifo_gtp.f -work oserdes_fifo
vmap pciegen2 "C:/Users/NineSun/Desktop/ov56401/project/pciegen2"
vlog -incr -f ./filelist_pciegen2_gtp.f -work pciegen2 -sv -mfcu
vmap pciegen3 "C:/Users/NineSun/Desktop/ov56401/project/pciegen3"
vlog -incr -f ./filelist_pciegen3_gtp.f -work pciegen3 -sv -mfcu

quit -force

# ----------------------------------------
