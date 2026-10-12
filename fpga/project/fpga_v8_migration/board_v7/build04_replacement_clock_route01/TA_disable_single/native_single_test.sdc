set_clock_groups -name {cmos1_pclk} -asynchronous -group [get_clocks {cmos1_pclk}] -disable
set_max_delay 15.238 -from [get_pins {source_diagnostics/cameras[0].source/mailbox[3]/opit_0_L6Q_LUT6DQL5Q_perm/CLK}] -to [get_pins {source_diagnostics/cameras[0].source/host_bank[0]/opit_0/D}]
