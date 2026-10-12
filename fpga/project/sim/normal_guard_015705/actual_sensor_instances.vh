reg_config #(.COLOR_BAR_TEST(COLOR_BAR_TEST))	coms1_reg_config(
    	.clk_25M                 (clk_25M            ),//input
    	.camera_rstn             (cmos1_reset        ),//input
    	.initial_en              (initial_en         ),//input
    	.i2c_sclk                (cfg1_scl          ),//output  (与诊断探针 AND 后接 cmos1_scl)
    	.i2c_sdat                (cmos1_sda          ),//inout
    	.reg_conf_done           (cmos_init_done_int[0]  ),//output config_finished
    	.reg_index               (                   ),//output reg [8:0]
    	.clock_20k               (                   ) //output reg
    );
reg_config #(.COLOR_BAR_TEST(COLOR_BAR_TEST))	coms2_reg_config(
    	.clk_25M                 (clk_25M            ),//input
    	.camera_rstn             (cmos2_reset        ),//input
    	.initial_en              (initial_en         ),//input
    	.i2c_sclk                (cfg2_scl          ),//output  (与诊断探针 AND 后接 cmos2_scl)
    	.i2c_sdat                (cmos2_sda          ),//inout
    	.reg_conf_done           (cmos_init_done_int[1]  ),//output config_finished
    	.reg_index               (                   ),//output reg [8:0]
    	.clock_20k               (                   ) //output reg
    );