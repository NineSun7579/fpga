create_clock -name {free_clk} [get_ports {free_clk}] -period {40.000} -waveform {0.000 20.000}
create_generated_clock -name {cam1_sccb} -source [get_ports {free_clk}] [get_pins {ov5640_top/ov5640/i2c_dri/dri_clk/Q}] -master_clock [get_clocks {free_clk}] -divide_by {24}
create_generated_clock -name {cam2_sccb} -source [get_ports {free_clk}] [get_pins {cam2_ov5640_top/ov5640/i2c_dri/dri_clk/Q}] -master_clock [get_clocks {free_clk}] -divide_by {24}
create_generated_clock -name {cam3_sccb} -source [get_ports {free_clk}] [get_pins {cam3_ov5640_top/ov5640/i2c_dri/dri_clk/Q}] -master_clock [get_clocks {free_clk}] -divide_by {24}
create_generated_clock -name {cam4_sccb} -source [get_ports {free_clk}] [get_pins {cam4_ov5640_top/ov5640/i2c_dri/dri_clk/Q}] -master_clock [get_clocks {free_clk}] -divide_by {24}
create_generated_clock -name {clk_150m} -source [get_ports {free_clk}] [get_pins {ov5640_clk/u_gpll/CLKOUT1}] -master_clock [get_clocks {free_clk}] -multiply_by {6} -divide_by {1}
create_clock -name {cmos1_pclk} [get_ports {cmos1_pclk}] -period {11.905} -waveform {0.000 5.952}
create_clock -name {cmos2_pclk} [get_ports {cmos2_pclk}] -period {11.905} -waveform {0.000 5.952}
create_clock -name {cmos3_pclk} [get_ports {cmos3_pclk}] -period {20.833} -waveform {0.000 10.416}
create_clock -name {cmos4_pclk} [get_ports {cmos4_pclk}] -period {20.833} -waveform {0.000 10.416}
set_clock_uncertainty {0.002} [get_clocks {cmos1_pclk}]  -setup -hold
set_clock_uncertainty {0.002} [get_clocks {cmos2_pclk}]  -setup -hold
set_clock_uncertainty {0.002} [get_clocks {cmos3_pclk}]  -setup -hold
set_clock_uncertainty {0.002} [get_clocks {cmos4_pclk}]  -setup -hold
create_generated_clock -name {rst_clk} -source [get_ports {free_clk}] [get_pins {ddr3/u_ddrphy_top/rst_clk_gpll/u_gpll/CLKOUT0}] -master_clock [get_clocks {free_clk}] -multiply_by {84} -divide_by {84}
create_generated_clock -name {ddrphy_sysclk} -source [get_ports {free_clk}] [get_pins {ddr3/u_ddrphy_top/ddrphy_gpll/u_gpll/CLKOUT0}] -master_clock [get_clocks {free_clk}] -multiply_by {84} -divide_by {16}
create_generated_clock -name {phy_dq_clk_0} -source [get_ports {free_clk}] [get_pins {ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/CLKOUTPHY}] -master_clock [get_clocks {free_clk}] -multiply_by {84} -divide_by {2}
create_generated_clock -name {phy_dq_sysclk_0} -source [get_pins {ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/CLKOUTPHY}] [get_pins {ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/CLKDIVOUT}] -master_clock [get_clocks {phy_dq_clk_0}] -edges {5 13 21} -edge_shift {0 0 0}
create_generated_clock -name {phy_dq_clk_1} -source [get_ports {free_clk}] [get_pins {ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[1].ddrphy_ppll/u_ppll/CLKOUTPHY}] -master_clock [get_clocks {free_clk}] -multiply_by {84} -divide_by {2}
create_generated_clock -name {phy_dq_sysclk_1} -source [get_pins {ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[1].ddrphy_ppll/u_ppll/CLKOUTPHY}] [get_pins {ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[1].u_ddrphy_ioclkdiv/CLKDIVOUT}] -master_clock [get_clocks {phy_dq_clk_1}] -edges {5 13 21} -edge_shift {0 0 0}
set_multicycle_path 2 -setup -from [get_clocks ddrphy_sysclk] -to [get_clocks phy_dq_sysclk_0]
set_multicycle_path 1 -hold -from [get_clocks ddrphy_sysclk] -to [get_clocks phy_dq_sysclk_0]
set_multicycle_path 2 -setup -from [get_clocks ddrphy_sysclk] -to [get_clocks phy_dq_sysclk_1]
set_multicycle_path 1 -hold -from [get_clocks ddrphy_sysclk] -to [get_clocks phy_dq_sysclk_1]
set_clock_uncertainty {0.4} -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {phy_dq_sysclk_0}] -setup -hold
set_clock_uncertainty {0.4} -from [get_clocks {phy_dq_sysclk_0}] -to [get_clocks {ddrphy_sysclk}] -setup -hold
set_clock_uncertainty {0.4} -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {phy_dq_sysclk_1}] -setup -hold
set_clock_uncertainty {0.4} -from [get_clocks {phy_dq_sysclk_1}] -to [get_clocks {ddrphy_sysclk}] -setup -hold
create_clock -name {pclk} [get_pins {pcie_fifo/pango_pcie_top/u_ips2l_pcie_wrap/U_IPS2L_PCIE_TOP/U_IPS2L_HSSTLP_PCIE_SOFT_PHY/x2.GTP_HSST_2LANE_TOP/U_GTP_HSSTLP_WRAPPER/CHANNEL1_ENABLE.U_GTP_HSSTLP_LANE1/P_TCLK2FABRIC}] -period {4.000} -waveform {0.000 2.000}
create_clock -name {pclk_div2} [get_pins {pcie_fifo/pango_pcie_top/u_ips2l_pcie_wrap/U_IPS2L_PCIE_TOP/U_IPS2L_HSSTLP_PCIE_SOFT_PHY/x2.GTP_HSST_2LANE_TOP/U_GTP_HSSTLP_WRAPPER/CHANNEL0_ENABLE.U_GTP_HSSTLP_LANE0/P_TCLK2FABRIC}] -period {8.000} -waveform {0.000 4.000}
create_clock -name {ref_clk} [get_pins {pcie_fifo/pango_pcie_top/u_ips2l_pcie_wrap/U_IPS2L_PCIE_TOP/U_IPS2L_HSSTLP_PCIE_SOFT_PHY/x2.GTP_HSST_2LANE_TOP/U_GTP_HSSTLP_WRAPPER/PLL0_ENABLE.U_GTP_HSSTLP_PLL0/P_REFCK2CORE}] -period {10.000} -waveform {0.000 5.000}
create_clock -name {sfp_fabric} [get_pins {u_sfp_rx_link/u_hsst/U_GTP_HSSTLP_WRAPPER/CHANNEL2_ENABLE.U_GTP_HSSTLP_LANE2/P_TCLK2FABRIC}] -period {8.000} -waveform {0.000 4.000}
set_clock_groups -name sfp_fabric -asynchronous -group [get_clocks {sfp_fabric}]
set_clock_groups -name clk_150m -asynchronous -group [get_clocks {clk_150m}]
set_clock_groups -name free_clk -asynchronous -group [get_clocks {free_clk}]
set_clock_groups -name rst_clk -asynchronous -group [get_clocks {rst_clk}]
set_clock_groups -name phy_dq_sysclk_0 -asynchronous -group [get_clocks {phy_dq_sysclk_0}]
set_clock_groups -name phy_dq_sysclk_1 -asynchronous -group [get_clocks {phy_dq_sysclk_1}]
set_clock_groups -name phy_dq_clk_0 -asynchronous -group [get_clocks {phy_dq_clk_0}]
set_clock_groups -name phy_dq_clk_1 -asynchronous -group [get_clocks {phy_dq_clk_1}]
set_clock_groups -name pclk -asynchronous -group [get_clocks {pclk}]
set_clock_groups -name pclk_div2 -asynchronous -group [get_clocks {pclk_div2}]
set_clock_groups -name ref_clk -asynchronous -group [get_clocks {ref_clk}]
set_clock_groups -asynchronous -group [get_clocks {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk}] -group [get_clocks {free_clk cam1_sccb cam2_sccb cam3_sccb cam4_sccb clk_150m rst_clk phy_dq_clk_0 phy_dq_sysclk_0 phy_dq_clk_1 phy_dq_sysclk_1 sfp_fabric pclk pclk_div2 ref_clk}]
set_clock_groups -asynchronous -group [get_clocks {ddrphy_sysclk}] -group [get_clocks {free_clk cam1_sccb cam2_sccb cam3_sccb cam4_sccb clk_150m rst_clk phy_dq_clk_0 phy_dq_sysclk_0 phy_dq_clk_1 phy_dq_sysclk_1 sfp_fabric pclk pclk_div2 ref_clk}]
set_false_path -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {cmos1_pclk}]
set_clock_groups -asynchronous -group [get_clocks {cmos1_pclk}] -group [get_clocks {cmos2_pclk}]
set_clock_groups -asynchronous -group [get_clocks {cmos1_pclk}] -group [get_clocks {cmos3_pclk}]
set_clock_groups -asynchronous -group [get_clocks {cmos1_pclk}] -group [get_clocks {cmos4_pclk}]
set_clock_groups -asynchronous -allow_paths -group [get_clocks {cmos1_pclk}] -group [get_clocks {ddrphy_sysclk}]
set_false_path -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {cmos2_pclk}]
set_clock_groups -asynchronous -group [get_clocks {cmos2_pclk}] -group [get_clocks {cmos3_pclk}]
set_clock_groups -asynchronous -group [get_clocks {cmos2_pclk}] -group [get_clocks {cmos4_pclk}]
set_clock_groups -asynchronous -allow_paths -group [get_clocks {cmos2_pclk}] -group [get_clocks {ddrphy_sysclk}]
set_false_path -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {cmos3_pclk}]
set_clock_groups -asynchronous -group [get_clocks {cmos3_pclk}] -group [get_clocks {cmos4_pclk}]
set_clock_groups -asynchronous -allow_paths -group [get_clocks {cmos3_pclk}] -group [get_clocks {ddrphy_sysclk}]
set_false_path -from [get_clocks {ddrphy_sysclk}] -to [get_clocks {cmos4_pclk}]
set_clock_groups -asynchronous -allow_paths -group [get_clocks {cmos4_pclk}] -group [get_clocks {ddrphy_sysclk}]
set_max_delay -datapath_only 15.238 -from [get_pins {source_diagnostics/cameras[0].source/mailbox[0]/CLK}] -to [get_pins {source_diagnostics/cameras[0].source/host_bank[0]/D}]
set_false_path -hold -from [get_pins {source_diagnostics/cameras[0].source/mailbox[0]/CLK}] -to [get_pins {source_diagnostics/cameras[0].source/host_bank[0]/D}]
