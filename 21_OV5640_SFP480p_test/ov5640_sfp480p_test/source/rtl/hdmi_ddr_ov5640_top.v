`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:Meyesemi
// Engineer: Will
//
// Create Date: 2023-03-17
// Design Name:
// Module Name: hdmi_ddr_ov5640_top
// Project Name: ov5640_sfp480p_test (由 10_HDMI_DDR3_OV5640_test 修改)
// Target Devices: Pango PGL50H (MES50HP 盘古50K)
// Description:
//      双目 OV5640 (640x480@60 RGB565 DVP) 逐行拼接为 1280x480 合成流
//      -> DDR3 帧缓存 -> 720p30 (1280x720@60, pix_clk=37.125MHz) 读出
//      -> MS7210 HDMI 输出双摄同屏 (左=CMOS1, 右=CMOS2)。
//      SFP0 光纤输出链路暂时注释保留 (搜索 "SFP0 光纤输出" 可恢复)。
// Dependencies:
//
// Revision:
// Revision 3.0 - 光口停用, HDMI 双摄同屏
//////////////////////////////////////////////////////////////////////////////////
`define UD #1
//两路摄像头同时启用: CMOS1 显示在左半屏, CMOS2 显示在右半屏

module hdmi_ddr_ov5640_top#(
	parameter MEM_ROW_ADDR_WIDTH   = 15         ,
	parameter MEM_COL_ADDR_WIDTH   = 10         ,
	parameter MEM_BADDR_WIDTH      = 3          ,
	parameter MEM_DQ_WIDTH         =  32        ,
	parameter MEM_DQS_WIDTH        =  32/8
)(
	input                                sys_clk              ,//50Mhz
//OV5647
    output  [1:0]                        cmos_init_done       ,//OV5640寄存器初始化完成
    //coms1
    inout                                cmos1_scl            ,//cmos1 i2c
    inout                                cmos1_sda            ,//cmos1 i2c
    input                                cmos1_vsync          ,//cmos1 vsync
    input                                cmos1_href           ,//cmos1 hsync refrence,data valid
    input                                cmos1_pclk           ,//cmos1 pxiel clock
    input   [7:0]                        cmos1_data           ,//cmos1 data
    output                               cmos1_reset          ,//cmos1 reset
    //coms2
    inout                                cmos2_scl            ,//cmos2 i2c
    inout                                cmos2_sda            ,//cmos2 i2c
    input                                cmos2_vsync          ,//cmos2 vsync
    input                                cmos2_href           ,//cmos2 hsync refrence,data valid
    input                                cmos2_pclk           ,//cmos2 pxiel clock
    input   [7:0]                        cmos2_data           ,//cmos2 data
    output                               cmos2_reset          ,//cmos2 reset
//DDR
    output                               mem_rst_n                 ,
    output                               mem_ck                    ,
    output                               mem_ck_n                  ,
    output                               mem_cke                   ,
    output                               mem_cs_n                  ,
    output                               mem_ras_n                 ,
    output                               mem_cas_n                 ,
    output                               mem_we_n                  ,
    output                               mem_odt                   ,
    output      [MEM_ROW_ADDR_WIDTH-1:0] mem_a                     ,
    output      [MEM_BADDR_WIDTH-1:0]    mem_ba                    ,
    inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs                   ,
    inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs_n                 ,
    inout       [MEM_DQ_WIDTH-1:0]       mem_dq                    ,
    output      [MEM_DQ_WIDTH/8-1:0]     mem_dm                    ,
    output reg                           heart_beat_led            ,
    output                               ddr_init_done             ,
//MS72xx (HDMI 输出)
    output                               rstn_out              ,//MS7210 复位(低有效)
    output                               iic_tx_scl            ,
    inout                                iic_tx_sda            ,
    output                               hdmi_int_led          ,//HDMI_OUT初始化完成
//HDMI_OUT
    output                               pix_clk               ,//37.125MHz 720p30
    output     reg                       vs_out                ,
    output     reg                       hs_out                ,
    output     reg                       de_out                ,
    output     reg[7:0]                  r_out                 ,
    output     reg[7:0]                  g_out                 ,
    output     reg[7:0]                  b_out
//SFP0 光纤输出 (暂时注释, 恢复时取消下行注释并同步恢复顶部逻辑/约束)
//    input                                sfp_refckp           ,//125MHz GT参考时钟(专用引脚,无需fdc约束)
//    input                                sfp_refckn           ,
//    input                                sfp0_rxp             ,//SFP0 RX(本设计未用)
//    input                                sfp0_rxn             ,
//    output                               sfp0_txp             ,//SFP0 TX 视频输出 (HSST CH2)
//    output                               sfp0_txn             ,
//    input                                sfp1_rxp             ,//SFP1 RX(本设计未用)
//    input                                sfp1_rxn             ,
//    output                               sfp1_txp             ,//SFP1 TX 发空闲码 (HSST CH3)
//    output                               sfp1_txn             ,
//    output                               sfp0_tx_disable      ,//SFP0 发射使能(低有效)
//    input                                sfp0_los             ,//SFP0 光信号丢失指示
//    output                               sfp_link_led          //链路就绪指示
);
/////////////////////////////////////////////////////////////////////////////////////
// ENABLE_DDR
    parameter CTRL_ADDR_WIDTH = MEM_ROW_ADDR_WIDTH + MEM_BADDR_WIDTH + MEM_COL_ADDR_WIDTH;//28
    parameter TH_1S = 27'd33000000;
/////////////////////////////////////////////////////////////////////////////////////
    wire                        pix_clk            ;//37.125MHz, 720p30 像素时钟
    wire                        cfg_clk            ;//10MHz
    wire                        clk_25M            ;//25MHz, 摄像头配置I2C时钟
    wire                        locked             ;
    wire                        core_clk           ;//DDR3 IP 输出时钟
    wire                        pll_lock           ;
    wire                        init_done          ;//fram_buf 初始化完成
    reg  [15:0]                 rstn_1ms            ;
    wire                        rstn_int            ;//内部上电复位(1ms后释放)
    wire                        cmos_scl            ;//cmos i2c clock
    wire                        cmos_sda            ;//cmos i2c data
    wire                        cmos_vsync          ;//cmos vsync
    wire                        cmos_href           ;//cmos hsync refrence,data valid
    wire                        cmos_pclk           ;//cmos pxiel clock
    wire   [7:0]                cmos_data           ;//cmos data
    wire                        cmos_reset          ;//cmos reset
    wire                        initial_en          ;
    wire[15:0]                  cmos1_d_16bit       ;
    wire                        cmos1_href_16bit    ;
    reg [7:0]                   cmos1_d_d0          ;
    reg                         cmos1_href_d0       ;
    reg                         cmos1_vsync_d0      ;
    wire                        cmos1_pclk_16bit    ;
    wire[15:0]                  cmos2_d_16bit       ;
    wire                        cmos2_href_16bit    ;
    reg [7:0]                   cmos2_d_d0          ;
    reg                         cmos2_href_d0       ;
    reg                         cmos2_vsync_d0      ;
    wire                        cmos2_pclk_16bit    ;
    wire[15:0]                  o_rgb565            ;//帧缓存读出像素(RGB565)
    wire                        vs_o                ;
    wire                        hs_o                ;
    wire                        de_o                ;
    wire[15:0]                  mrg_c_data          ;//双摄合成流
    wire                        mrg_c_de            ;
    wire                        mrg_c_vs            ;
    wire                        de_re               ;
    wire [11:0]                 y_act               ;//显示行号(用于只读前480行)
//axi bus
    wire [CTRL_ADDR_WIDTH-1:0]  axi_awaddr                 ;
    wire                        axi_awuser_ap              ;
    wire [3:0]                  axi_awuser_id              ;
    wire [3:0]                  axi_awlen                  ;
    wire                        axi_awready                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire                        axi_awvalid                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire [MEM_DQ_WIDTH*8-1:0]   axi_wdata                  ;
    wire [MEM_DQ_WIDTH*8/8-1:0] axi_wstrb                  ;
    wire                        axi_wready                 ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire [3:0]                  axi_wusero_id              ;
    wire                        axi_wusero_last            ;
    wire [CTRL_ADDR_WIDTH-1:0]  axi_araddr                 ;
    wire                        axi_aruser_ap              ;
    wire [3:0]                  axi_aruser_id              ;
    wire [3:0]                  axi_arlen                  ;
    wire                        axi_arready                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire                        axi_arvalid                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire [MEM_DQ_WIDTH*8-1:0]   axi_rdata                   /* synthesis syn_keep = 1 */;
    wire                        axi_rvalid                  /* synthesis syn_keep = 1 */;
    wire [3:0]                  axi_rid                    ;
    wire                        axi_rlast                  ;
    reg  [26:0]                 cnt                        ;
/////////////////////////////////////////////////////////////////////////////////////
//PLL
    pll u_pll (
        .clkin1   (  sys_clk    ),//50MHz
        .clkout0  (  pix_clk    ),//37.125M 720p30
        .clkout1  (  cfg_clk    ),//10MHz
        .clkout2  (  clk_25M    ),//25M
        .pll_lock (  locked     )
    );

    always @(posedge cfg_clk)
    begin
    	if(!locked)
    	    rstn_1ms <= 16'd0;
    	else
    	begin
    		if(rstn_1ms == 16'h2710)
    		    rstn_1ms <= rstn_1ms;
    		else
    		    rstn_1ms <= rstn_1ms + 1'b1;
    	end
    end

    assign rstn_int  = (rstn_1ms == 16'h2710);//上电1ms后释放
    assign rstn_out  = rstn_int;               //MS7210 复位(兼作内部复位)

//配置CMOS///////////////////////////////////////////////////////////////////////////////////
//OV5640 register configure enable
    power_on_delay	power_on_delay_inst(
    	.clk_50M                 (sys_clk        ),//input
    	.reset_n                 (1'b1           ),//input
    	.camera1_rstn            (cmos1_reset    ),//output
    	.camera2_rstn            (cmos2_reset    ),//output
    	.camera_pwnd             (               ),//output
    	.initial_en              (initial_en     ) //output
    );
//CMOS1 Camera
    reg_config	coms1_reg_config(
    	.clk_25M                 (clk_25M            ),//input
    	.camera_rstn             (cmos1_reset        ),//input
    	.initial_en              (initial_en         ),//input
    	.i2c_sclk                (cmos1_scl          ),//output
    	.i2c_sdat                (cmos1_sda          ),//inout
    	.reg_conf_done           (cmos_init_done[0]  ),//output config_finished
    	.reg_index               (                   ),//output reg [8:0]
    	.clock_20k               (                   ) //output reg
    );

//CMOS2 Camera
    reg_config	coms2_reg_config(
    	.clk_25M                 (clk_25M            ),//input
    	.camera_rstn             (cmos2_reset        ),//input
    	.initial_en              (initial_en         ),//input
    	.i2c_sclk                (cmos2_scl          ),//output
    	.i2c_sdat                (cmos2_sda          ),//inout
    	.reg_conf_done           (cmos_init_done[1]  ),//output config_finished
    	.reg_index               (                   ),//output reg [8:0]
    	.clock_20k               (                   ) //output reg
    );
//CMOS 8bit转16bit///////////////////////////////////////////////////////////////////////////////////
//CMOS1
    always@(posedge cmos1_pclk)
        begin
            cmos1_d_d0        <= cmos1_data    ;
            cmos1_href_d0     <= cmos1_href    ;
            cmos1_vsync_d0    <= cmos1_vsync   ;
        end

    cmos_8_16bit cmos1_8_16bit(
    	.pclk           (cmos1_pclk       ),//input
    	.rst_n          (cmos_init_done[0]),//input
    	.pdata_i        (cmos1_d_d0       ),//input[7:0]
    	.de_i           (cmos1_href_d0    ),//input
    	.vs_i           (cmos1_vsync_d0    ),//input

    	.pixel_clk      (cmos1_pclk_16bit ),//output
    	.pdata_o        (cmos1_d_16bit    ),//output[15:0]
    	.de_o           (cmos1_href_16bit ) //output
    );
//CMOS2
    always@(posedge cmos2_pclk)
        begin
            cmos2_d_d0        <= cmos2_data    ;
            cmos2_href_d0     <= cmos2_href    ;
            cmos2_vsync_d0    <= cmos2_vsync   ;
        end

    cmos_8_16bit cmos2_8_16bit(
    	.pclk           (cmos2_pclk       ),//input
    	.rst_n          (cmos_init_done[1]),//input
    	.pdata_i        (cmos2_d_d0       ),//input[7:0]
    	.de_i           (cmos2_href_d0    ),//input
    	.vs_i           (cmos2_vsync_d0    ),//input

    	.pixel_clk      (cmos2_pclk_16bit ),//output
    	.pdata_o        (cmos2_d_16bit    ),//output[15:0]
    	.de_o           (cmos2_href_16bit ) //output
    );
/////////////////////////////////////////////////////////////////////////////////////
//双目逐行拼接: 左半屏=CMOS1, 右半屏=CMOS2, 合成 1280x480@60 流
//(RGB565 通道重排在 cam2_merge 内部寄存级完成)
    cam2_merge #(
        .LINE_PIX (12'd640),
        .LINES    (12'd480)
    ) u_cam2_merge (
        .a_clk   (  cmos1_pclk_16bit                    ),//A域 42MHz
        .a_rst_n (  cmos_init_done[0]                   ),
        .a_data  (  cmos1_d_16bit                       ),
        .a_de    (  cmos1_href_16bit                    ),
        .a_vs    (  cmos1_vsync_d0                      ),
        .b_clk   (  cmos2_pclk_16bit                    ),//B域 42MHz
        .b_rst_n (  cmos_init_done[1]                   ),
        .b_data  (  cmos2_d_16bit                       ),
        .b_de    (  cmos2_href_16bit                    ),
        .b_vs    (  cmos2_vsync_d0                      ),
        .o_clk   (  core_clk                            ),//公共域: DDR core 100MHz
        .o_rst_n (  ddr_init_done                       ),
        .c_data  (  mrg_c_data                          ),
        .c_de    (  mrg_c_de                            ),
        .c_vs    (  mrg_c_vs                            )
    );
//修改ddr读写模块v1 (H_NUM=1280: 一行写入左640+右640)
    fram_buf fram_buf(
        .ddr_clk        (  core_clk             ),//input                         ddr_clk,
        .ddr_rstn       (  ddr_init_done        ),//input                         ddr_rstn,
        //data_in
.vin_clk        (  core_clk             ),//input  合成流在 core_clk 域,
        .wr_fsync       (  mrg_c_vs             ),//input                         wr_fsync,
        .wr_en          (  mrg_c_de             ),//input                         wr_en,
        .wr_data        (  mrg_c_data           ),//input  [15 : 0]  wr_data,
        //data_out
        .vout_clk       (  pix_clk              ),//input                         vout_clk,
        .rd_fsync       (  vs_o                 ),//input                         rd_fsync,
        .rd_en          (  de_re & (y_act < 12'd480) ),//input  只读前480行(双摄高度)
        .vout_de        (  de_o                 ),//output                        vout_de,
        .vout_data      (  o_rgb565             ),//output [PIX_WIDTH- 1'b1 : 0]  vout_data,
        .init_done      (  init_done            ),//output reg                    init_done,
        //axi bus
        .axi_awaddr     (  axi_awaddr           ),// output[27:0]
        .axi_awid       (  axi_awuser_id        ),// output[3:0]
        .axi_awlen      (  axi_awlen            ),// output[3:0]
        .axi_awsize     (                       ),// output[2:0]
        .axi_awburst    (                       ),// output[1:0]
        .axi_awready    (  axi_awready          ),// input
        .axi_awvalid    (  axi_awvalid          ),// output
        .axi_wdata      (  axi_wdata            ),// output[255:0]
        .axi_wstrb      (  axi_wstrb            ),// output[31:0]
        .axi_wlast      (  axi_wusero_last      ),// input
        .axi_wvalid     (                       ),// output
        .axi_wready     (  axi_wready           ),// input
        .axi_bid        (  4'd0                 ),// input[3:0]
        .axi_araddr     (  axi_araddr           ),// output[27:0]
        .axi_arid       (  axi_aruser_id        ),// output[3:0]
        .axi_arlen      (  axi_arlen            ),// output[3:0]
        .axi_arsize     (                       ),// output[2:0]
        .axi_arburst    (                       ),// output[1:0]
        .axi_arvalid    (  axi_arvalid          ),// output
        .axi_arready    (  axi_arready          ),// input
        .axi_rready     (                       ),// output
        .axi_rdata      (  axi_rdata            ),// input[255:0]
        .axi_rvalid     (  axi_rvalid           ),// input
        .axi_rlast      (  axi_rlast            ),// input
        .axi_rid        (  axi_rid              ) // input[3:0]
    );
/////////////////////////////////////////////////////////////////////////////////////
//产生vga时序 720p30 (pix_clk=37.125MHz)
     sync_vg sync_vg(
        .clk            (  pix_clk              ),//input                   clk,
        .rstn           (  init_done            ),//input                   rstn,
        .vs_out         (  vs_o                 ),//output reg              vs_out,
        .hs_out         (  hs_o                 ),//output reg              hs_out,
        .de_out         (                       ),//output reg              de_out,
        .de_re          (  de_re                ),
        .y_act          (  y_act                )
    );
/////////////////////////////////////////////////////////////////////////////////////
//HDMI 输出寄存器
     always@(posedge pix_clk) begin
        r_out<={o_rgb565[15:11],3'b0   };
        g_out<={o_rgb565[10:5],2'b0    };
        b_out<={o_rgb565[4:0],3'b0     };
        vs_out<=vs_o;
        hs_out<=hs_o;
        de_out<=de_o;
     end
//配置7210
    wire init_over_tx;
    wire init_over_rx;
    wire iic_scl;
    wire iic_sda;

    ms72xx_ctl ms72xx_ctl(
        .clk             (  cfg_clk        ), //input       clk,
        .rst_n           (  rstn_out       ), //input       rstn,
        .init_over_tx    (  init_over_tx   ), //output      init_over,
        .init_over_rx    (  init_over_rx   ), //output      init_over,
        .iic_tx_scl      (  iic_tx_scl     ), //output      iic_scl,
        .iic_tx_sda      (  iic_tx_sda     ), //inout       iic_sda
        .iic_scl         (  iic_scl        ), //output      iic_scl,
        .iic_sda         (  iic_sda        )  //inout       iic_sda
    );
    assign hdmi_int_led = init_over_tx;

/* SFP0 光纤输出 (暂时注释, 恢复时取消本段注释, 顶层端口注释, 以及 .fdc 中
   HSST/SFP 约束注释, 并把 build.tcl/.pds 中 hsst_test IP 保持登记即可)
/////////////////////////////////////////////////////////////////////////////////////
    wire        clk2core_tx      ;
    wire        hsst_pll_lock    ;
    wire        hsst_tx_done_2   ;
    wire [31:0] sfp_tx_d         ;
    wire [3:0]  sfp_tx_k         ;
    wire        hsst_link_ready  = hsst_pll_lock & hsst_tx_done_2;

    assign sfp0_tx_disable = 1'b0;
    assign sfp_link_led    = hsst_link_ready & ~sfp0_los;

    reg [1:0] fab_rst_sync = 2'b00;
    always @(posedge clk2core_tx)
        fab_rst_sync <= {fab_rst_sync[0], rstn_int};
    wire fab_rst_n = fab_rst_sync[1];

    sfp_video_tx u_sfp_video_tx(
        .vid_clk    (  pix_clk           ),
        .vid_rst_n  (  rstn_int & locked ),
        .vid_data   (  {vs_o, hs_o, de_o, o_rgb565} ),
        .fab_clk    (  clk2core_tx       ),
        .fab_rst_n  (  fab_rst_n         ),
        .link_ready (  hsst_link_ready   ),
        .txd        (  sfp_tx_d          ),
        .txk        (  sfp_tx_k          )
    );

    hsst_test u_hsst(
        .i_free_clk          (  sys_clk        ),
        .i_p_refckp_0        (  sfp_refckp     ),
        .i_p_refckn_0        (  sfp_refckn     ),
        .i_wtchdg_clr_0      (  ~rstn_int      ),
        .o_wtchdg_st_0       (                 ),
        .o_pll_done_0        (                 ),
        .o_txlane_done_2     (  hsst_tx_done_2 ),
        .o_txlane_done_3     (                 ),
        .o_rxlane_done_2     (                 ),
        .o_rxlane_done_3     (                 ),
        .o_p_clk2core_tx_2   (  clk2core_tx    ),
        .i_p_tx2_clk_fr_core (  clk2core_tx    ),
        .i_p_tx3_clk_fr_core (  clk2core_tx    ),
        .i_p_rx2_clk_fr_core (  clk2core_tx    ),
        .i_p_rx3_clk_fr_core (  clk2core_tx    ),
        .o_p_pll_lock_0      (  hsst_pll_lock  ),
        .o_p_rx_sigdet_sta_2 (                 ),
        .o_p_rx_sigdet_sta_3 (                 ),
        .o_p_lx_cdr_align_2  (                 ),
        .o_p_lx_cdr_align_3  (                 ),
        .o_p_pcs_lsm_synced_2(                 ),
        .o_p_pcs_lsm_synced_3(                 ),
        .i_p_l2rxn           (  sfp0_rxn       ),
        .i_p_l2rxp           (  sfp0_rxp       ),
        .i_p_l3rxn           (  sfp1_rxn       ),
        .i_p_l3rxp           (  sfp1_rxp       ),
        .o_p_l2txn           (  sfp0_txn       ),
        .o_p_l2txp           (  sfp0_txp       ),
        .o_p_l3txn           (  sfp1_txn       ),
        .o_p_l3txp           (  sfp1_txp       ),
        .i_txd_2             (  sfp_tx_d       ),
        .i_tdispsel_2        (  4'b0           ),
        .i_tdispctrl_2       (  4'b0           ),
        .i_txk_2             (  sfp_tx_k       ),
        .i_txd_3             (  32'hBC0028BC   ),
        .i_tdispsel_3        (  4'b0           ),
        .i_tdispctrl_3       (  4'b0           ),
        .i_txk_3             (  4'b1001        ),
        .o_rxstatus_2        (                 ),
        .o_rxd_2             (                 ),
        .o_rdisper_2         (                 ),
        .o_rdecer_2          (                 ),
        .o_rxk_2             (                 ),
        .o_rxstatus_3        (                 ),
        .o_rxd_3             (                 ),
        .o_rdisper_3         (                 ),
        .o_rdecer_3          (                 ),
        .o_rxk_3             (                 ),
        .i_pll_rst_0         (  ~rstn_int      )
    );
SFP0 光纤输出注释结束 */

/////////////////////////////////////////////////////////////////////////////////////
//ddr
        DDR3_50H u_DDR3_50H (
             .ref_clk                   (sys_clk            ),
             .resetn                    (rstn_int           ),// input
             .ddr_init_done             (ddr_init_done      ),// output
             .ddrphy_clkin              (core_clk           ),// output
             .pll_lock                  (pll_lock           ),// output

             .axi_awaddr                (axi_awaddr         ),// input [27:0]
             .axi_awuser_ap             (1'b0               ),// input
             .axi_awuser_id             (axi_awuser_id      ),// input [3:0]
             .axi_awlen                 (axi_awlen          ),// input [3:0]
             .axi_awready               (axi_awready        ),// output
             .axi_awvalid               (axi_awvalid        ),// input
             .axi_wdata                 (axi_wdata          ),
             .axi_wstrb                 (axi_wstrb          ),// input [31:0]
             .axi_wready                (axi_wready         ),// output
             .axi_wusero_id             (                   ),// output [3:0]
             .axi_wusero_last           (axi_wusero_last    ),// output
             .axi_araddr                (axi_araddr         ),// input [27:0]
             .axi_aruser_ap             (1'b0               ),// input
             .axi_aruser_id             (axi_aruser_id      ),// input [3:0]
             .axi_arlen                 (axi_arlen          ),// input [3:0]
             .axi_arready               (axi_arready        ),// output
             .axi_arvalid               (axi_arvalid        ),// input
             .axi_rdata                 (axi_rdata          ),// output [255:0]
             .axi_rid                   (axi_rid            ),// output [3:0]
             .axi_rlast                 (axi_rlast          ),// output
             .axi_rvalid                (axi_rvalid         ),// output

             .apb_clk                   (1'b0               ),// input
             .apb_rst_n                 (1'b1               ),// input
             .apb_sel                   (1'b0               ),// input
             .apb_enable                (1'b0               ),// input
             .apb_addr                  (8'b0               ),// input [7:0]
             .apb_write                 (1'b0               ),// input
             .apb_ready                 (                   ), // output
             .apb_wdata                 (16'b0              ),// input [15:0]
             .apb_rdata                 (                   ),// output [15:0]
             .apb_int                   (                   ),// output

             .mem_rst_n                 (mem_rst_n          ),// output
             .mem_ck                    (mem_ck             ),// output
             .mem_ck_n                  (mem_ck_n           ),// output
             .mem_cke                   (mem_cke            ),// output
             .mem_cs_n                  (mem_cs_n           ),// output
             .mem_ras_n                 (mem_ras_n          ),// output
             .mem_cas_n                 (mem_cas_n          ),// output
             .mem_we_n                  (mem_we_n           ),// output
             .mem_odt                   (mem_odt            ),// output
             .mem_a                     (mem_a              ),// output [14:0]
             .mem_ba                    (mem_ba             ),// output [2:0]
             .mem_dqs                   (mem_dqs            ),// inout [3:0]
             .mem_dqs_n                 (mem_dqs_n          ),// inout [3:0]
             .mem_dq                    (mem_dq             ),// inout [31:0]
             .mem_dm                    (mem_dm             ),// output [3:0]
             //debug
             .debug_data                (                   ),// output [135:0]
             .debug_slice_state         (                   ),// output [51:0]
             .debug_calib_ctrl          (                   ),// output [21:0]
             .ck_dly_set_bin            (                   ),// output [7:0]
             .force_ck_dly_en           (1'b0               ),// input
             .force_ck_dly_set_bin      (8'h05              ),// input [7:0]
             .dll_step                  (                   ),// output [7:0]
             .dll_lock                  (                   ),// output
             .init_read_clk_ctrl        (2'b0               ),// input [1:0]
             .init_slip_step            (4'b0               ),// input [3:0]
             .force_read_clk_ctrl       (1'b0               ),// input
             .ddrphy_gate_update_en     (1'b0               ),// input
             .update_com_val_err_flag   (                   ),// output [3:0]
             .rd_fake_stop              (1'b0               ) // input
       );

//心跳信号
     always@(posedge core_clk) begin
        if (!ddr_init_done)
            cnt <= 27'd0;
        else if ( cnt >= TH_1S )
            cnt <= 27'd0;
        else
            cnt <= cnt + 27'd1;
     end

     always @(posedge core_clk)
        begin
        if (!ddr_init_done)
            heart_beat_led <= 1'd1;
        else if ( cnt >= TH_1S )
            heart_beat_led <= ~heart_beat_led;
    end

/////////////////////////////////////////////////////////////////////////////////////
endmodule
