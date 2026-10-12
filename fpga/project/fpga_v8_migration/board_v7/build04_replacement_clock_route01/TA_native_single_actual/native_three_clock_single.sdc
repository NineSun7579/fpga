create_clock -name {free_clk} [get_ports {free_clk}] -period 40.000 -waveform {0.000 20.000}
create_clock -name {cmos1_pclk} [get_ports {cmos1_pclk}] -period 11.905 -waveform {0.000 5.952}
set_clock_uncertainty 0.002 [get_clocks {cmos1_pclk}] -setup -hold
create_generated_clock -name {ddrphy_sysclk} -source [get_ports {free_clk}] [get_pins {ddr3/u_ddrphy_top/ddrphy_gpll/u_gpll/gpll_inst/CLKOUT0}] -master_clock [get_clocks {free_clk}] -multiply_by 84 -divide_by 16
set_max_delay 15.238 -from [get_pins {source_diagnostics/cameras[0].source/mailbox[3]/opit_0_L6Q_LUT6DQL5Q_perm/CLK}] -to [get_pins {source_diagnostics/cameras[0].source/host_bank[0]/opit_0/D}]
