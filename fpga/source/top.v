// ==========================================
// ��ƵԴ����ѡ���뱣������һ����ע�͵���һ��
// ==========================================
 `define USE_OV5640
//`define USE_HDMI


module top #(
    parameter   MSI_NUM = 5,
    parameter   AXI_ID_LEN      = 4, 
                AXI_ID_M_LEN    = $clog2(7) + AXI_ID_LEN,
		        AXI_DATA_LEN    = 128, 
		        AXI_DATA_SIZE   = $clog2(AXI_DATA_LEN/8), 	        
		        AXI_STRB_LEN    = AXI_DATA_LEN / 8, 
                AXI_ADDR_WIDTH  = 32,  
                BURST_LEN = 16, // [ZEROFIX 2026-09-19] 16-beat bursts = IP max awlen+1 = FIFO depth;
                                // the staging gate then requires a FULL FIFO before the AW
                                // is presented, so the IP can never consume an empty slot
                                // (that produced the 8-on/8-off zero blocks in DDR).
                                // prior: BURST_LEN = 8,  // [WATERFIX2 2026-09-19] 16-beat bursts into the 16-deep ddr_fifo16_w
                                // had zero slack: one stalled drain cycle dropped a W beat and
                                // the DDR3 IP (never seeing awlen+1 beats) killed the whole M00
                                // write path. 8-beat bursts + the free-space AW gate leave 2x room.
                                // with single-beat bursts (every beat needs its own B
                                // before the next is issued). 16-beat bursts cut the B
                                // demand 16x and keep one outstanding txn per master.
                                // [ZDIAG 2026-09-18] old '=16 stripes unchanged' verdict
                                // predates the ledger fix and is not applicable.

    //DDR3
    parameter  MEM_ROW_WIDTH    = 15         ,
               MEM_COLUMN_WIDTH = 10         ,
               MEM_BANK_WIDTH   = 3          ,
               MEM_DQ_WIDTH     = 16         ,
               MEM_DQS_WIDTH    = 2          ,
               CTRL_ADDR_WIDTH  = MEM_ROW_WIDTH + MEM_BANK_WIDTH + MEM_COLUMN_WIDTH
)(

    input                       free_clk         /* synthesis PAP_MARK_DEBUG="<3/c0/0>" */,       //25MHZ
    input                       button_rst_n    ,

    ////////////////// PCIE ////////////////
    input                       perst_n         ,
    input                       ref_clk_n       ,      
    input                       ref_clk_p       ,      
    input           [1:0]       rxn             ,
    input           [1:0]       rxp             ,
    output  wire    [1:0]       txn             ,
    output  wire    [1:0]       txp             ,
    output wire                 ref_led         ,
    output wire                 pclk_led        ,
    // output wire                 smlh_link_up     ,
    // output wire                 rdlh_link_up     ,



    ////////////DDR3
    output                               mem_cs_n                  ,  
    output                               mem_rst_n                 ,
    output                               mem_ck                    ,
    output                               mem_ck_n                  ,
    output                               mem_cke                   ,
    output                               mem_ras_n                 ,
    output                               mem_cas_n                 ,
    output                               mem_we_n                  ,
    output                               mem_odt                   ,
    output      [MEM_ROW_WIDTH-1:0]      mem_a                     ,
    output      [MEM_BANK_WIDTH-1:0]     mem_ba                    ,
    inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs                   ,
    inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs_n                 ,
    inout       [MEM_DQ_WIDTH-1:0]       mem_dq                    ,
    output      [MEM_DQ_WIDTH/8-1:0]     mem_dm                    ,

    output reg                           heart_beat_led            ,

`ifdef USE_OV5640
    /////////////CAM
    input                                cmos1_pclk               /* synthesis PAP_MARK_DEBUG="<1/c0/0>,<3/t0/0>" */, 
    input                                cmos1_vsync              /* synthesis PAP_MARK_DEBUG="<1/t0/0>,<3/t0/1>" */, 
    input                                cmos1_href               /* synthesis PAP_MARK_DEBUG="<1/t0/1>,<3/t0/2>" */, 
    input       [7 : 0]                  cmos1_data              , 
    output                               cmos1_rst_n             , 
    // output                               cmos1_pwdn              , 
    output                               cmos1_scl               , 
    inout                                cmos1_sda               ,                 



    /////////////CAM2 (FMC 2nd DVP camera)
    input                                cmos2_pclk               /* synthesis PAP_MARK_DEBUG="<2/c0/0>,<3/t0/3>" */, 
    input                                cmos2_vsync              /* synthesis PAP_MARK_DEBUG="<2/t0/0>,<3/t0/4>" */, 
    input                                cmos2_href               /* synthesis PAP_MARK_DEBUG="<2/t0/1>,<3/t0/5>" */, 
    input       [7 : 0]                  cmos2_data              , 
    output                               cmos2_rst_n             , 
    output                               cmos2_scl               , 
    inout                                cmos2_sda                 
`elsif USE_HDMI
    /////////////////////////  HDMI
    //ms72XX
    output            rstn_out,

    // FMC I2C 
    output            iic_scl,
    inout             iic_sda, 

    // output            iic_tx_scl,
    // inout             iic_tx_sda, 

    //HDMI IN
    input             pixclk_in ,                            
    input             vs_in     , 
    input             hs_in     , 
    input             de_in     ,
    input     [7:0]   r_in      , 
    input     [7:0]   g_in      , 
    input     [7:0]   b_in      
`endif
);

    wire clk_50m, clk_150m, clk_10m, locked;


///////////////////////////// AXI wires between crossbar and DDR3 ///////////////////////////
wire [27:0]                 ddr_axi_awaddr     /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_awuser_ap  ;
wire [AXI_ID_M_LEN-1:0]     ddr_axi_awuser_id  /* synthesis PAP_MARK_DEBUG="true" */;
wire [3:0]                  ddr_axi_awlen      /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_awready    /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_awvalid    /* synthesis PAP_MARK_DEBUG="true" */;
wire [2:0]                  ddr_axi_awsize     /* synthesis PAP_MARK_DEBUG="true" */;
wire [1:0]                  ddr_axi_awburst    /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_awlock     ;
wire [3:0]                  ddr_axi_awcache    ;
wire [2:0]                  ddr_axi_awprot     ;
wire [3:0]                  ddr_axi_awqos      ;

wire [AXI_DATA_LEN-1:0]     ddr_axi_wdata      /* synthesis PAP_MARK_DEBUG="true" */;
wire [AXI_DATA_LEN-1:0]     ddr_axi_wdata_ddr3      ;
wire [AXI_STRB_LEN-1:0]     ddr_axi_wstrb      /* synthesis PAP_MARK_DEBUG="true" */;
wire [AXI_STRB_LEN-1:0]     ddr_axi_wstrb_ddr3      ;
wire                        ddr_axi_fifo_full/* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_wvalid     /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_wready_ddr3    ;
wire [AXI_ID_LEN-1:0]       ddr_axi_wusero_id  /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_wusero_last_ddr3;
wire                        ddr_axi_wlast      /* synthesis PAP_MARK_DEBUG="true" */;

wire [1:0]                  ddr_axi_bresp      /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_bvalid     /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_bready     /* synthesis PAP_MARK_DEBUG="true" */;
wire [AXI_ID_M_LEN-1:0]     ddr_axi_bid        /* synthesis PAP_MARK_DEBUG="true" */;



wire [27:0]                 ddr_axi_araddr     ;
wire                        ddr_axi_aruser_ap  ;
wire [AXI_ID_M_LEN-1:0]     ddr_axi_aruser_id  ;
wire [AXI_DATA_LEN-1:0]     ddr_axi_aruser     ;
wire [3:0]                  ddr_axi_arlen      ;
wire                        ddr_axi_arready    /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_arvalid    ;

wire [AXI_DATA_LEN-1:0]     ddr_axi_rdata      /* synthesis PAP_MARK_DEBUG="true" */;
wire [AXI_DATA_LEN-1:0]     ddr_axi_rdata_ddr3;
wire [AXI_ID_M_LEN-1:0]     ddr_axi_rid        /* synthesis PAP_MARK_DEBUG="true" */;
wire [AXI_ID_LEN-1:0]       ddr_axi_rid_ddr3;
wire                        ddr_axi_rlast      /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_rlast_ddr3;
wire                        ddr_axi_rvalid     /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_rvalid_ddr3;
wire                        ddr_axi_rready     /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_fifo_empty;





wire [2:0]                  ddr_axi_arsize     /* synthesis PAP_MARK_DEBUG="true" */;
wire [1:0]                  ddr_axi_arburst    /* synthesis PAP_MARK_DEBUG="true" */;
wire                        ddr_axi_arlock     /* synthesis PAP_MARK_DEBUG="true" */;
wire [3:0]                  ddr_axi_arcache    /* synthesis PAP_MARK_DEBUG="true" */;
wire [2:0]                  ddr_axi_arprot     /* synthesis PAP_MARK_DEBUG="true" */;
wire [3:0]                  ddr_axi_arqos      /* synthesis PAP_MARK_DEBUG="true" */;
wire [1:0]                  ddr_axi_rresp      /* synthesis PAP_MARK_DEBUG="true" */;


wire [1:0]                  ddr_axi_buser      ;
wire [1:0]                  ddr_axi_ruser      ;
wire [1:0]                  ddr_axi_awuser     ;
wire [1:0]                  ddr_axi_wuser      ;


/////////////////////////////     DDR3   ///////////////////////////////////////////////////
parameter TH_1S = 27'd33000000;
reg  [26:0]                 cnt                        ;
always@(posedge core_clk or negedge ddr_init_done) begin
   if (!ddr_init_done)
      cnt <= 27'd0;
   else if ( cnt >= TH_1S )
      cnt <= 27'd0;
   else
      cnt <= cnt + 27'd1;
end

always @(posedge core_clk or negedge ddr_init_done) begin
   if (!ddr_init_done)
      heart_beat_led <= 1'd1;
   else if ( cnt >= TH_1S )
      heart_beat_led <= ~heart_beat_led;
end

wire [4:0] wr_water_level;
wire       w_fifo_empty;   // [AWFIX 2026-09-19] declared early: used by the FIFO port map below
ddr_fifo16_w ddr_fifo16_w (
  .wr_data({ddr_axi_wstrb, ddr_axi_wdata}),              // input [143:0]
  .wr_en(ddr_axi_wvalid),                  // input
  .wr_water_level(wr_water_level),    // output [4:0]
  .full(ddr_axi_fifo_full),                    // output
  .almost_full(),      // output
  .rd_data({ddr_axi_wstrb_ddr3, ddr_axi_wdata_ddr3}),              // output [143:0]
  .rd_en(ddr_axi_wready_ddr3),                  // input
  .empty(w_fifo_empty),      // output  [AWFIX 2026-09-19]
  .almost_empty(),    // output
  .clk(axi_clk),                      // input
  .rst(axi_rst)                       // input
);



ddr_fifo16_r ddr_fifo16_r (
  .wr_data({ddr_axi_rid_ddr3, ddr_axi_rlast_ddr3, ddr_axi_rdata_ddr3}),              // input [132:0]
  .wr_en(ddr_axi_rvalid_ddr3),                  // input
  .full(),                    // output
  .almost_full(),      // output
  .rd_data({ddr_axi_rid[AXI_ID_LEN-1 : 0], ddr_axi_rlast, ddr_axi_rdata}),              // output [132:0]
  .rd_en(ddr_axi_rready),                  // input
  .empty(ddr_axi_fifo_empty),                  // output
  .almost_empty(),    // output
  .clk(axi_clk),                      // input
  .rst(axi_rst)                       // input
);
assign ddr_axi_rid[AXI_ID_M_LEN-1 : AXI_ID_LEN] = ddr_axi_ar_sid[AXI_ID_M_LEN-1 : AXI_ID_LEN];

// [AWFIX 2026-09-19] the old water-gate REGISTER re-evaluated awvalid every cycle
// while waiting for the IP's awready: a closing gate RETRACTED an already-asserted
// awvalid (AXI violation). Worse, the crossbar's awready was tied straight to the
// IP's awready, so whenever the gate blocked while the IP idled ready-high, the
// crossbar retired the AW into the void: the IP never saw the burst, its W beats
// drained unpaired, wusero_last never came and the fabric-minted B (below) never
// rose -- the permanent M00 write wedge. Replaced by latch-and-hold shims defined
// after the B-channel bridge.


ddr3 #(
    .MEM_ROW_WIDTH              (MEM_ROW_WIDTH                ),
    .MEM_COLUMN_WIDTH           (MEM_COLUMN_WIDTH             ),
    .MEM_BANK_WIDTH             (MEM_BANK_WIDTH               ),
    .MEM_DQ_WIDTH               (MEM_DQ_WIDTH                 ),
    .MEM_DM_WIDTH               (MEM_DQS_WIDTH                ),
    .MEM_DQS_WIDTH              (MEM_DQS_WIDTH                ),
    .CTRL_ADDR_WIDTH            (CTRL_ADDR_WIDTH              )
  )
ddr3(
    .ref_clk                    (free_clk                     ),
    .resetn                     (button_rst_n                 ),

    .core_clk                   (core_clk                     ),
    .ddr_init_done              (ddr_init_done                ),

    .pll_lock                   (                             ),
    .phy_pll_lock               (                             ),
    .gpll_lock                  (                             ),
    .rst_gpll_lock              (                             ),
    .ddrphy_cpd_lock            (                             ),

    .axi_awaddr                 (ddr3_aw_addr                  ), // [AWFIX]
    .axi_awuser_ap              (ddr3_aw_ap                    ),
    .axi_awuser_id              (ddr3_aw_id                    ),
    .axi_awlen                  (ddr3_aw_len                   ),
    .axi_awready                (ddr_axi_awready               ),
    .axi_awvalid                (ddr3_aw_v                     ),

    .axi_wdata                  (ddr_axi_wdata_ddr3            ),
    .axi_wstrb                  (ddr_axi_wstrb_ddr3            ),
    .axi_wready                 (ddr_axi_wready_ddr3           ),
    .axi_wusero_id              (ddr_axi_wusero_id             ),
    .axi_wusero_last            (ddr_axi_wusero_last_ddr3      ),

    .axi_araddr                 (ddr3_ar_addr                  ), // [ARFIX]
    .axi_aruser_ap              (ddr3_ar_ap                    ),
    .axi_aruser_id              (ddr3_ar_id                    ),
    .axi_arlen                  (ddr3_ar_len                   ),
    .axi_arready                (ddr_axi_arready               ),
    .axi_arvalid                (ddr3_ar_v                     ),

    .axi_rdata                  (ddr_axi_rdata_ddr3                 ),
    .axi_rid                    (ddr_axi_rid_ddr3                   ),
    .axi_rlast                  (ddr_axi_rlast_ddr3                 ),
    .axi_rvalid                 (ddr_axi_rvalid_ddr3                ),

    .apb_clk                    (1'b0                         ),
    .apb_rst_n                  (1'b0                         ),
    .apb_sel                    (1'b0                         ),
    .apb_enable                 (1'b0                         ),
    .apb_addr                   (8'd0                         ),
    .apb_write                  (1'b0                         ),
    .apb_ready                  (                             ),
    .apb_wdata                  (16'd0                        ),
    .apb_rdata                  (                             ),

    .mem_cs_n                   (mem_cs_n                     ),
    .mem_rst_n                  (mem_rst_n                    ),
    .mem_ck                     (mem_ck                       ),
    .mem_ck_n                   (mem_ck_n                     ),
    .mem_cke                    (mem_cke                      ),
    .mem_ras_n                  (mem_ras_n                    ),
    .mem_cas_n                  (mem_cas_n                    ),
    .mem_we_n                   (mem_we_n                     ),
    .mem_odt                    (mem_odt                      ),
    .mem_a                      (mem_a                        ),
    .mem_ba                     (mem_ba                       ),
    .mem_dqs                    (mem_dqs                      ),
    .mem_dqs_n                  (mem_dqs_n                    ),
    .mem_dq                     (mem_dq                       ),
    .mem_dm                     (mem_dm                       ),

    .dbg_gate_start             (1'b0                         ),
    .dbg_cpd_start              (1'b0                         ),
    .dbg_ddrphy_rst_n           (1'b1                         ),
    .dbg_gpll_scan_rst          (1'b0                         ),

    .samp_position_dyn_adj      (1'b0                         ),
    .init_samp_position_even    (16'd0                        ),
    .init_samp_position_odd     (16'd0                        ),

    .wrcal_position_dyn_adj     (1'b0                         ),
    .init_wrcal_position        (16'd0                        ),

    .force_read_clk_ctrl        (1'b0                         ),
    .init_slip_step             (8'd0                         ),
    .init_read_clk_ctrl         (6'd0                         ),

    .debug_calib_ctrl           (                             ),
    .dbg_dll_upd_state          (                             ),
    .dbg_slice_status           (                             ),
    .dbg_slice_state            (                             ),
    .debug_data                 (                             ),
    .debug_gpll_dps_phase       (                             ),

    .dbg_rst_dps_state          (                             ),
    .dbg_tran_err_rst_cnt       (                             ),
    .dbg_ddrphy_init_fail       (                             ),

    .debug_cpd_offset_adj       (1'b0                         ),
    .debug_cpd_offset_dir       (1'b0                         ),
    .debug_cpd_offset           (10'd0                        ),
    .debug_dps_cnt_dir0         (                             ),
    .debug_dps_cnt_dir1         (                             ),

    .ck_dly_en                  (1'b0                         ),
    .init_ck_dly_step           (8'd0                         ),
    .ck_dly_set_bin             (                             ),

    .align_error                (                             ),
    .debug_rst_state            (                             ),
    .debug_cpd_state            (                             )
  );

wire axi_clk;
wire axi_rst;
assign axi_clk = core_clk;
assign axi_rst = ~ddr_init_done;

/////////////////////////////////////// [WARB 2026-09-19] camera write arbiter ///////
// Single-outstanding 2-master arbiter replacing the crossbar M00 write path.
// Bench-proven: 9741 consecutive bursts, zero wedge (sim/wedge/tb_wedge.v).
wire [3:0]   arb_s_awid;
wire [31:0]  arb_s_awaddr;
wire [7:0]   arb_s_awlen;
wire [2:0]   arb_s_awsize, arb_s_awprot;
wire [1:0]   arb_s_awburst;
wire         arb_s_awlock;
wire [3:0]   arb_s_awcache;
wire         arb_s_awvalid, arb_s_awready;
wire [127:0] arb_s_wdata;
wire [15:0]  arb_s_wstrb;
wire         arb_s_wlast, arb_s_wvalid, arb_s_wready;
wire [3:0]   arb_s_bid;
wire [1:0]   arb_s_bresp;
wire         arb_s_bvalid, arb_s_bready;
// parked crossbar M00 write ports
wire [6:0]   arb2x_awid;
wire [31:0]  arb2x_awaddr;
wire [7:0]   arb2x_awlen;
wire [2:0]   arb2x_awsize, arb2x_awprot;
wire [1:0]   arb2x_awburst;
wire         arb2x_awlock;
wire [3:0]   arb2x_awcache;
wire [3:0]   arb2x_awqos;
wire [1:0]   arb2x_awuser;
wire         arb2x_awvalid;
wire [127:0] arb2x_wdata;
wire [15:0]  arb2x_wstrb;
wire         arb2x_wlast, arb2x_wvalid;
wire [1:0]   arb2x_wuser;
ddr_w_arb u_ddr_w_arb (
    .clk(axi_clk), .rst(axi_rst),
    .m0_awid    (ov5640_axi_awid    ), .m0_awaddr (ov5640_axi_awaddr ),
    .m0_awlen   (ov5640_axi_awlen   ), .m0_awsize (ov5640_axi_awsize ),
    .m0_awburst (ov5640_axi_awburst ), .m0_awlock (ov5640_axi_awlock ),
    .m0_awcache (ov5640_axi_awcache ), .m0_awprot (ov5640_axi_awprot ),
    .m0_awvalid (ov5640_axi_awvalid ), .m0_awready(ov5640_axi_awready),
    .m0_wdata   (ov5640_axi_wdata   ), .m0_wstrb  (ov5640_axi_wstrb  ),
    .m0_wlast   (ov5640_axi_wlast   ), .m0_wvalid (ov5640_axi_wvalid ),
    .m0_wready  (ov5640_axi_wready  ),
    .m0_bid     (ov5640_axi_bid     ), .m0_bresp  (ov5640_axi_bresp  ),
    .m0_bvalid  (ov5640_axi_bvalid  ), .m0_bready (ov5640_axi_bready ),
    .m1_awid    (cam2_axi_awid      ), .m1_awaddr (cam2_axi_awaddr   ),
    .m1_awlen   (cam2_axi_awlen     ), .m1_awsize (cam2_axi_awsize   ),
    .m1_awburst (cam2_axi_awburst   ), .m1_awlock (cam2_axi_awlock   ),
    .m1_awcache (cam2_axi_awcache   ), .m1_awprot (cam2_axi_awprot   ),
    .m1_awvalid (cam2_axi_awvalid   ), .m1_awready(cam2_axi_awready  ),
    .m1_wdata   (cam2_axi_wdata     ), .m1_wstrb  (cam2_axi_wstrb    ),
    .m1_wlast   (cam2_axi_wlast     ), .m1_wvalid (cam2_axi_wvalid   ),
    .m1_wready  (cam2_axi_wready    ),
    .m1_bid     (cam2_axi_bid       ), .m1_bresp  (cam2_axi_bresp    ),
    .m1_bvalid  (cam2_axi_bvalid    ), .m1_bready (cam2_axi_bready   ),
    .s_awid     (arb_s_awid         ), .s_awaddr (arb_s_awaddr      ),
    .s_awlen    (arb_s_awlen        ), .s_awsize (arb_s_awsize      ),
    .s_awburst  (arb_s_awburst      ), .s_awlock (arb_s_awlock      ),
    .s_awcache  (arb_s_awcache      ), .s_awprot (arb_s_awprot      ),
    .s_awvalid  (arb_s_awvalid      ), .s_awready(arb_s_awready     ),
    .s_wdata    (arb_s_wdata        ), .s_wstrb  (arb_s_wstrb       ),
    .s_wlast    (arb_s_wlast        ), .s_wvalid (arb_s_wvalid      ),
    .s_wready   (arb_s_wready       ),
    .s_bid      (arb_s_bid          ), .s_bresp  (arb_s_bresp       ),
    .s_bvalid   (arb_s_bvalid       ), .s_bready (arb_s_bready      )
);
// DDR glue AW/W side now fed by the arbiter
assign ddr_axi_awaddr     = arb_s_awaddr;
assign ddr_axi_awlen      = arb_s_awlen;
assign ddr_axi_awvalid    = arb_s_awvalid;
assign arb_s_awready      = ddr_axi_awready_xbar;
assign ddr_axi_wdata      = arb_s_wdata;
assign ddr_axi_wstrb      = arb_s_wstrb;
assign ddr_axi_wlast      = arb_s_wlast;
assign ddr_axi_wvalid     = arb_s_wvalid;
assign arb_s_wready       = !ddr_axi_fifo_full;
assign arb_s_bvalid       = ddr_axi_bvalid;
assign arb_s_bresp        = ddr_axi_bresp;
assign ddr_axi_bready     = arb_s_bready;
// awuser id now carries the arbiter's source id (m0=0001, m1=0100 4-bit form)
assign ddr_axi_awuser_id  = {3'b000, arb_s_awid};
assign ddr_axi_awuser_ap  = 1'b0;
assign arb_s_bid          = {3'b000, 1'b0};

/////////////////////////////////////// DDR3 B-Channel Bridge //////////////////////////////////////
reg  [AXI_ID_M_LEN-1 : AXI_ID_LEN]                  ddr_axi_aw_sid        ;//ddr_axi_awuser_id??3?
reg  [AXI_ID_M_LEN-1 : AXI_ID_LEN]                  ddr_axi_ar_sid        ;//ddr_axi_aruser_id??3?

// latch aw_sid on AW handshake
always @(posedge axi_clk) begin
    if (axi_rst) begin
        ddr_axi_aw_sid <= {(AXI_ID_M_LEN - AXI_ID_LEN){1'b0}};
    end 
    else if (ddr_axi_awvalid && ddr_axi_awready_xbar) begin   // [AWFIX] ack at latch
        ddr_axi_aw_sid <= ddr_axi_awuser_id[AXI_ID_M_LEN-1 : AXI_ID_LEN];
    end
end

// latch ar_sid on AR handshake
always @(posedge axi_clk) begin
    if (axi_rst) begin
        ddr_axi_ar_sid <= {(AXI_ID_M_LEN - AXI_ID_LEN){1'b0}};
    end 
    else if (ddr_axi_arvalid && ddr_axi_arready_xbar) begin   // [ARFIX] ack at latch
        ddr_axi_ar_sid <= ddr_axi_aruser_id[AXI_ID_M_LEN-1 : AXI_ID_LEN];
    end
end


reg                         ddr_axi_bvalid_int    ;
reg  [1:0]                  ddr_axi_bresp_int     ;
reg  [AXI_ID_M_LEN-1:0]     ddr_axi_bid_int       ;
always @(posedge axi_clk) begin
    if (axi_rst) begin
        ddr_axi_bvalid_int  <= 1'b0;
        ddr_axi_bresp_int   <= 2'b01;
        ddr_axi_bid_int <= {AXI_ID_M_LEN{1'b0}};
    end 
    else begin
        if (ddr_axi_wready_ddr3 && ddr_axi_wusero_last_ddr3) begin
            ddr_axi_bvalid_int <= 1'b1;
            ddr_axi_bresp_int  <= 2'b00;
            ddr_axi_bid_int <= {ddr_axi_aw_sid[AXI_ID_M_LEN-1 : AXI_ID_LEN], ddr_axi_wusero_id};
        end 
        else if (ddr_axi_bvalid && ddr_axi_bready) begin
            ddr_axi_bvalid_int <= 1'b0;
            ddr_axi_bresp_int  <= 2'b01;
            ddr_axi_bid_int <= {AXI_ID_M_LEN{1'b0}};
        end
    end
end

assign ddr_axi_bvalid = ddr_axi_bvalid_int;
assign ddr_axi_bresp  = ddr_axi_bresp_int;
assign ddr_axi_bid    = ddr_axi_bid_int;

/////////////////////////////////////// DDR3 AW/AR latch shims [AWFIX/ARFIX 2026-09-19] ///
// Proper single-handshake adapters between the crossbar and the DDR3 IP.
// The crossbar is acknowledged exactly when we latch a request; the request is
// then HELD with stable payload until the IP accepts (AXI-legal, no retraction).
// Single-outstanding end-to-end (no held request + write FIFO empty + no pending
// B for AW; read FIFO empty for AR) also keeps the aw_sid/ar_sid ID rebuilds sane.
// [STAGE 2026-09-19] The DDR3 IP's W channel is UNTHROTTLEABLE: it pulses
// wready at its own pace and counts awlen+1 beats itself (see the IP's own
// example_design -- there is no wvalid at all). Presenting an AW before its
// beats are in the FIFO let the IP consume GHOST beats from an empty FIFO;
// the real beats then stranded in the FIFO forever and blocked all later AWs
// (the permanent M00 write wedge). Hold each latched AW until its ENTIRE
// burst is staged in the FIFO, then present it: during IP consumption the
// FIFO only drains, so every demanded beat is guaranteed present.
wire aw_burst_fits   = (ddr_axi_awlen < (5'd16 - wr_water_level));
wire aw_latch_now    = ddr_axi_awvalid && !ddr3_aw_v && !aw_hold_v
                       && w_fifo_empty && aw_burst_fits && !ddr_axi_bvalid_int;
wire ar_latch_now    = ddr_axi_arvalid && !ddr3_ar_v && ddr_axi_fifo_empty;

reg              ddr3_aw_v, ddr3_ar_v;
reg              aw_hold_v;
reg [27:0]       ddr3_aw_addr, ddr3_ar_addr;
reg [3:0]        ddr3_aw_len,  ddr3_ar_len;
reg              ddr3_aw_ap,   ddr3_ar_ap;
reg [AXI_ID_M_LEN-1:0] ddr3_aw_id, ddr3_ar_id;

wire aw_stage_ok = (wr_water_level >= ({1'b0, ddr3_aw_len} + 5'd1)) && !w_fifo_empty;

always @(posedge axi_clk) begin
    if (axi_rst) begin
        aw_hold_v <= 1'b0;
        ddr3_aw_v <= 1'b0;
    end
    else begin
        if (aw_latch_now) begin
            aw_hold_v   <= 1'b1;
            ddr3_aw_addr <= ddr_axi_awaddr[27:0];
            ddr3_aw_len  <= ddr_axi_awlen;
            ddr3_aw_ap   <= ddr_axi_awuser_ap;
            ddr3_aw_id   <= ddr_axi_awuser_id;
        end
        if (aw_hold_v && !ddr3_aw_v && aw_stage_ok) begin
            aw_hold_v <= 1'b0;
            ddr3_aw_v <= 1'b1;
        end
        else if (ddr3_aw_v && ddr_axi_awready) begin
            ddr3_aw_v <= 1'b0;
        end
    end
end
always @(posedge axi_clk) begin
    if (axi_rst) ddr3_ar_v <= 1'b0;
    else if (ar_latch_now)                       ddr3_ar_v <= 1'b1;
    else if (ddr3_ar_v && ddr_axi_arready)       ddr3_ar_v <= 1'b0;
end
always @(posedge axi_clk) begin
    if (ar_latch_now) begin
        ddr3_ar_addr <= ddr_axi_araddr[27:0];
        ddr3_ar_len  <= ddr_axi_arlen;
        ddr3_ar_ap   <= ddr_axi_aruser_ap;
        ddr3_ar_id   <= ddr_axi_aruser_id;
    end
end
// crossbar-facing readies: acknowledge exactly at latch time
wire ddr_axi_awready_xbar = aw_latch_now;
wire ddr_axi_arready_xbar = ar_latch_now;


/////////////////////////////     DDR3   ///////////////////////////////////////////////////
    wire       [AXI_ID_LEN-1:0]       pcie_axi_awid   ;
    wire       [31:0]                 pcie_axi_awaddr ;
    wire       [ 3:0]                 pcie_axi_awlen  ;
    wire       [ 2:0]                 pcie_axi_awsize ;
    wire       [ 1:0]                 pcie_axi_awburst;
    wire                              pcie_axi_awlock ;
    wire       [ 3:0]                 pcie_axi_awcache;
    wire       [ 2:0]                 pcie_axi_awprot ;
    wire       [ 3:0]                 pcie_axi_awqos  ;
    wire                              pcie_axi_awvalid;
    wire                              pcie_axi_awready;

    wire       [AXI_DATA_LEN-1:0]     pcie_axi_wdata  ;
    wire       [AXI_STRB_LEN-1:0]     pcie_axi_wstrb  ;
    wire                              pcie_axi_wlast  ;
    wire                              pcie_axi_wvalid ;
    wire                              pcie_axi_wready ;

    wire       [AXI_ID_LEN-1:0]       pcie_axi_bid    ;
    wire       [ 1:0]                 pcie_axi_bresp  ;
    wire                              pcie_axi_bvalid ;
    wire                              pcie_axi_bready ;

    wire       [AXI_ID_LEN-1:0]       pcie_axi_arid   ;
    wire       [31:0]                 pcie_axi_araddr ;
    wire       [ 3:0]                 pcie_axi_arlen  ;
    wire       [ 2:0]                 pcie_axi_arsize ;
    wire       [ 1:0]                 pcie_axi_arburst;
    wire                              pcie_axi_arlock ;
    wire       [ 3:0]                 pcie_axi_arcache;
    wire       [ 2:0]                 pcie_axi_arprot ;
    wire       [ 3:0]                 pcie_axi_arqos  ;
    wire                              pcie_axi_arvalid;
    wire                              pcie_axi_arready;

    wire       [AXI_ID_LEN-1:0]       pcie_axi_rid    ;
    wire       [AXI_DATA_LEN-1:0]     pcie_axi_rdata  ;
    wire       [ 1:0]                 pcie_axi_rresp  ;
    wire                              pcie_axi_rlast  ;
    wire                              pcie_axi_rvalid ;
    wire                              pcie_axi_rready ;

    wire                              pcie_clk        ;
    wire                              pcie_rst        ;

    wire [MSI_NUM-2 : 0]      msi_req       ;
    wire [MSI_NUM-2 : 0]      msi_grant     ;


    assign msi_req = {1'd0, 1'b0, 2'b00}; //[MSIFIX 2026-09-13] freerun: xdma_req stuck high = MSI storm, camera MSI off

pcie_fifo #(
    .MSI_NUM(MSI_NUM)
)
pcie_fifo(    

    .button_rst_n(button_rst_n)    ,

    ////////////////// PCIE ////////////////
    .perst_n     (perst_n     )    ,
    .ref_clk_n   (ref_clk_n   )    ,      
    .ref_clk_p   (ref_clk_p   )    ,      
    .rxn         (rxn         )    ,
    .rxp         (rxp         )    ,
    .txn         (txn         )    ,
    .txp         (txp         )    ,
    .ref_led     (ref_led     )    ,
    .pclk_led    (pclk_led    )    ,
    // .smlh_link_up(smlh_link_up)    ,
    // .rdlh_link_up(rdlh_link_up)    ,

    .fifo_pcie_clk(pcie_clk   )    ,
    .fifo_pcie_rst(pcie_rst   )    ,

    .i_msi_req  (msi_req     )     ,
    .o_msi_grant(msi_grant   )     ,
    ///////////////// AXI FOR DDR3 //////////////////////////////
    .axi_clk(axi_clk),
    .axi_rst(axi_rst),

    .axi_awid   (pcie_axi_awid   )     ,
    .axi_awaddr (pcie_axi_awaddr )     ,
    .axi_awlen  (pcie_axi_awlen  )     ,
    .axi_awsize (pcie_axi_awsize )     ,
    .axi_awburst(pcie_axi_awburst)     ,
    .axi_awlock (pcie_axi_awlock )     ,
    .axi_awcache(pcie_axi_awcache)     ,
    .axi_awprot (pcie_axi_awprot )     ,
    .axi_awqos  (pcie_axi_awqos  )     ,
    .axi_awvalid(pcie_axi_awvalid)     ,
    .axi_awready(pcie_axi_awready)     ,
    
    .axi_wdata  (pcie_axi_wdata  )     ,
    .axi_wstrb  (pcie_axi_wstrb  )     ,
    .axi_wlast  (pcie_axi_wlast  )     ,
    .axi_wvalid (pcie_axi_wvalid )     ,
    .axi_wready (pcie_axi_wready )     ,
    
    .axi_bid    (pcie_axi_bid    )     ,
    .axi_bresp  (pcie_axi_bresp  )     ,
    .axi_bvalid (pcie_axi_bvalid )     ,
    .axi_bready (pcie_axi_bready )     ,
    
    .axi_arid   (pcie_axi_arid   )     ,
    .axi_araddr (pcie_axi_araddr )     ,
    .axi_arlen  (pcie_axi_arlen  )     ,
    .axi_arsize (pcie_axi_arsize )     ,
    .axi_arburst(pcie_axi_arburst)     ,
    .axi_arlock (pcie_axi_arlock )     ,
    .axi_arcache(pcie_axi_arcache)     ,
    .axi_arprot (pcie_axi_arprot )     ,
    .axi_arqos  (pcie_axi_arqos  )     ,
    .axi_arvalid(pcie_axi_arvalid)     ,
    .axi_arready(pcie_axi_arready)     ,
    
    .axi_rid    (pcie_axi_rid    )     ,
    .axi_rdata  (pcie_axi_rdata  )     ,
    .axi_rresp  (pcie_axi_rresp  )     ,
    .axi_rlast  (pcie_axi_rlast  )     ,
    .axi_rvalid (pcie_axi_rvalid )     ,
    .axi_rready (pcie_axi_rready )           
);


/////////////////////////////////   CMD    ////////////////////////////////////////////////
ov5640_clk ov5640_clk(
  .clkout2(clk_10m),
  .clkout1(clk_150m),      // output 150M
  .clkout0(),             //[CLKFIX 2026-09-13] PLL bypassed (never locks @25MHz in)

  .lock(locked),          // output
  .clkin1(free_clk)         // input
);

//[CLKFIX 2026-09-13] i2c domain runs on free_clk directly (25MHz)
assign clk_50m = free_clk;

///////////////////////////// AXI-Lite wires for ovreg ///////////////////////////
wire [31:0]                 ovreg_axil_awaddr   ;
wire                        ovreg_axil_awvalid  ;
wire                        ovreg_axil_awready  ;
wire [31:0]                 ovreg_axil_wdata    ;
wire [3:0]                  ovreg_axil_wstrb    ;
wire                        ovreg_axil_wvalid   ;
wire                        ovreg_axil_wready   ;
wire [1:0]                  ovreg_axil_bresp    ;
wire                        ovreg_axil_bvalid   ;
wire                        ovreg_axil_bready   ;
wire [31:0]                 ovreg_axil_araddr   ;
wire                        ovreg_axil_arvalid  ;
wire                        ovreg_axil_arready  ;
wire [31:0]                 ovreg_axil_rdata    ;
wire [1:0]                  ovreg_axil_rresp    ;
wire                        ovreg_axil_rvalid   ;
wire                        ovreg_axil_rready   ;

// --- CAM segment (decoder m0, addr[8]=0: 0x2000_0000~0x2000_00FF -> ov5640_reg) ---
wire                        cam_axil_awvalid, cam_axil_awready;
wire [31:0]                 cam_axil_awaddr;
wire                        cam_axil_wvalid, cam_axil_wready;
wire [31:0]                 cam_axil_wdata;
wire [3:0]                  cam_axil_wstrb;
wire                        cam_axil_bvalid, cam_axil_bready;
wire [1:0]                  cam_axil_bresp;
wire                        cam_axil_arvalid, cam_axil_arready;
wire [31:0]                 cam_axil_araddr;
wire                        cam_axil_rvalid, cam_axil_rready;
wire [31:0]                 cam_axil_rdata;
wire [1:0]                  cam_axil_rresp;

// --- cam2 register window (M01 sub-window 0x2000_0200~0x02FF) ---
wire                        cam2_axil_awvalid, cam2_axil_awready;
wire [31:0]                 cam2_axil_awaddr;
wire                        cam2_axil_wvalid, cam2_axil_wready;
wire [31:0]                 cam2_axil_wdata;
wire [3:0]                  cam2_axil_wstrb;
wire                        cam2_axil_bvalid, cam2_axil_bready;
wire [1:0]                  cam2_axil_bresp;
wire                        cam2_axil_arvalid, cam2_axil_arready;
wire [31:0]                 cam2_axil_araddr;
wire                        cam2_axil_rvalid, cam2_axil_rready;
wire [31:0]                 cam2_axil_rdata;
wire [1:0]                  cam2_axil_rresp;

// --- cam2 capture / write stream (S04) ---
wire [31 : 0]               cam2_cmd_addr    ;
wire [31 : 0]               cam2_cmd_len     ;
wire                        cam2_cmd_valid   ;
wire                        cam2_cmd_ready   ;
wire [AXI_DATA_LEN-1 : 0]   cam2_s_data      ;
wire                        cam2_s_data_valid;
wire                        cam2_s_data_last ;
wire                        cam2_s_data_ready;
wire [AXI_ID_LEN-1:0]   cam2_axi_awid    ;
wire [31:0]             cam2_axi_awaddr  ;
wire [3:0]              cam2_axi_awlen   ;
wire [2:0]              cam2_axi_awsize  ;
wire [1:0]              cam2_axi_awburst ;
wire                    cam2_axi_awlock  ;
wire [3:0]              cam2_axi_awcache ;
wire [2:0]              cam2_axi_awprot  ;
wire                    cam2_axi_awvalid ;
wire                    cam2_axi_awready ;
wire [AXI_DATA_LEN-1:0] cam2_axi_wdata   ;
wire [AXI_STRB_LEN-1:0] cam2_axi_wstrb   ;
wire                    cam2_axi_wlast   ;
wire                    cam2_axi_wvalid  ;
wire                    cam2_axi_wready  ;
wire [AXI_ID_LEN-1:0]   cam2_axi_bid     ;
wire [1:0]              cam2_axi_bresp   ;
wire                    cam2_axi_bvalid  ;
wire                    cam2_axi_bready  ;

// --- PREP segment (decoder m1, addr[8]=1: 0x2000_0100~0x2000_01FF -> prep_regs) ---
wire                        prep_axil_awvalid, prep_axil_awready;
wire [31:0]                 prep_axil_awaddr;
wire                        prep_axil_wvalid, prep_axil_wready;
wire [31:0]                 prep_axil_wdata;
wire [3:0]                  prep_axil_wstrb;
wire                        prep_axil_bvalid, prep_axil_bready;
wire [1:0]                  prep_axil_bresp;
wire                        prep_axil_arvalid, prep_axil_arready;
wire [31:0]                 prep_axil_araddr;
wire                        prep_axil_rvalid, prep_axil_rready;
wire [31:0]                 prep_axil_rdata;
wire [1:0]                  prep_axil_rresp;

///////////////////////////// ovreg_axi signals ///////////////////////////
wire [AXI_ID_M_LEN-1:0]     ovreg_axi_awid     ;
wire [31:0]                 ovreg_axi_awaddr   ;
wire [3:0]                  ovreg_axi_awlen    ;
wire [2:0]                  ovreg_axi_awsize   ;
wire [1:0]                  ovreg_axi_awburst  ;
wire                        ovreg_axi_awlock   ;
wire [3:0]                  ovreg_axi_awcache  ;
wire [2:0]                  ovreg_axi_awprot   ;
wire [3:0]                  ovreg_axi_awqos    ;
wire [3:0]                  ovreg_axi_awregion ;
wire                        ovreg_axi_awvalid  ;
wire                        ovreg_axi_awready  ;

wire [AXI_DATA_LEN-1:0]     ovreg_axi_wdata     ;
wire [AXI_STRB_LEN-1:0]     ovreg_axi_wstrb     ;
wire                        ovreg_axi_wlast     ;
wire                        ovreg_axi_wvalid    ;
wire                        ovreg_axi_wready    ;

wire [AXI_ID_M_LEN-1:0]     ovreg_axi_bid       ;
wire [1:0]                  ovreg_axi_bresp     ;
wire                        ovreg_axi_bvalid    ;
wire                        ovreg_axi_bready    ;

wire [AXI_ID_M_LEN-1:0]     ovreg_axi_arid     ;
wire [31:0]                 ovreg_axi_araddr   ;
wire [3:0]                  ovreg_axi_arlen    ;
wire [2:0]                  ovreg_axi_arsize   ;
wire [1:0]                  ovreg_axi_arburst  ;
wire                        ovreg_axi_arlock   ;
wire [3:0]                  ovreg_axi_arcache  ;
wire [2:0]                  ovreg_axi_arprot   ;
wire [3:0]                  ovreg_axi_arqos    ;
wire [3:0]                  ovreg_axi_arregion ;
wire                        ovreg_axi_arvalid  ;
wire                        ovreg_axi_arready  ;

wire [AXI_DATA_LEN-1:0]     ovreg_axi_rdata    ;
wire [AXI_ID_M_LEN-1:0]     ovreg_axi_rid      ;
wire [1:0]                  ovreg_axi_rresp    ;
wire                        ovreg_axi_rlast    ;
wire                        ovreg_axi_rvalid   ;
wire                        ovreg_axi_rready   ;


axi_to_axi_lite #(
    .AXI_ID_LEN(AXI_ID_M_LEN)
)
axi_to_axi_lite(
    .axi_clk(axi_clk),
    .axi_rst(axi_rst),
    // ==========================================
    // ??? AXI Slave  (128-bit)
    // ==========================================
    .s_axi_awid    (ovreg_axi_awid    ),
    .s_axi_awaddr  (ovreg_axi_awaddr  ),
    .s_axi_awlen   (ovreg_axi_awlen   ),
    .s_axi_awsize  (ovreg_axi_awsize  ),
    .s_axi_awburst (ovreg_axi_awburst ),
    .s_axi_awlock  (ovreg_axi_awlock  ),
    .s_axi_awcache (ovreg_axi_awcache ),
    .s_axi_awprot  (ovreg_axi_awprot  ),
    .s_axi_awqos   (ovreg_axi_awqos   ),
    .s_axi_awregion(ovreg_axi_awregion),
    .s_axi_awvalid (ovreg_axi_awvalid ),
    .s_axi_awready (ovreg_axi_awready ),

    .s_axi_wdata   (ovreg_axi_wdata  ),
    .s_axi_wstrb   (ovreg_axi_wstrb  ),
    .s_axi_wlast   (ovreg_axi_wlast  ),
    .s_axi_wvalid  (ovreg_axi_wvalid ),
    .s_axi_wready  (ovreg_axi_wready ),

    .s_axi_bid     (ovreg_axi_bid    ),
    .s_axi_bresp   (ovreg_axi_bresp  ),
    .s_axi_bvalid  (ovreg_axi_bvalid ),
    .s_axi_bready  (ovreg_axi_bready ),

    .s_axi_arid    (ovreg_axi_arid   ),
    .s_axi_araddr  (ovreg_axi_araddr ),
    .s_axi_arlen   (ovreg_axi_arlen  ),
    .s_axi_arsize  (ovreg_axi_arsize ),
    .s_axi_arburst (ovreg_axi_arburst),
    .s_axi_arlock  (ovreg_axi_arlock ),
    .s_axi_arcache (ovreg_axi_arcache),
    .s_axi_arprot  (ovreg_axi_arprot ),
    .s_axi_arqos   (ovreg_axi_arqos  ),
    .s_axi_arregion(ovreg_axi_arregion),
    .s_axi_arvalid (ovreg_axi_arvalid),
    .s_axi_arready (ovreg_axi_arready),

    .s_axi_rid     (ovreg_axi_rid    ),
    .s_axi_rdata   (ovreg_axi_rdata  ),
    .s_axi_rresp   (ovreg_axi_rresp  ),
    .s_axi_rlast   (ovreg_axi_rlast  ),
    .s_axi_rvalid  (ovreg_axi_rvalid ),
    .s_axi_rready  (ovreg_axi_rready ),


    // ==========================================
    // AXI-Lite Master  (32-bit)
    // ==========================================
    .m_axil_awaddr (ovreg_axil_awaddr ),
    .m_axil_awvalid(ovreg_axil_awvalid),
    .m_axil_awready(ovreg_axil_awready),

    .m_axil_wdata  (ovreg_axil_wdata  ),
    .m_axil_wstrb  (ovreg_axil_wstrb  ),
    .m_axil_wvalid (ovreg_axil_wvalid ),
    .m_axil_wready (ovreg_axil_wready ),

    .m_axil_bresp  (ovreg_axil_bresp  ),
    .m_axil_bvalid (ovreg_axil_bvalid ),
    .m_axil_bready (ovreg_axil_bready ),

    .m_axil_araddr (ovreg_axil_araddr ),
    .m_axil_arvalid(ovreg_axil_arvalid),
    .m_axil_arready(ovreg_axil_arready),

    .m_axil_rdata  (ovreg_axil_rdata  ),
    .m_axil_rresp  (ovreg_axil_rresp  ),
    .m_axil_rvalid (ovreg_axil_rvalid ),
    .m_axil_rready (ovreg_axil_rready )
);


wire [31 : 0]               cam_cmd_addr    /*synthesis PAP_MARK_DEBUG="1"*/;
wire [31 : 0]               cam_cmd_len     /*synthesis PAP_MARK_DEBUG="1"*/;
wire                        cam_cmd_valid   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                        cam_cmd_ready   /*synthesis PAP_MARK_DEBUG="1"*/;

wire [AXI_DATA_LEN-1 : 0]   cam_s_data      /*synthesis PAP_MARK_DEBUG="1"*/;
// preprocess tap (camera raw stream -> preprocess -> processed write)
wire [AXI_DATA_LEN-1 : 0]   cam_tap_data    ;
wire                        cam_tap_data_valid;
wire                        cam_tap_data_last ;
wire                        cam_tap_data_ready;
wire                        cam_s_data_valid/*synthesis PAP_MARK_DEBUG="1"*/;
wire                        cam_s_data_last /*synthesis PAP_MARK_DEBUG="1"*/;
wire                        cam_s_data_ready/*synthesis PAP_MARK_DEBUG="1"*/;

wire [1 : 0]                cam_irq;     

// --- AXI-Lite address decoder: splits M01 window by addr[8] ---
//   addr[8]=0 -> ov5640_reg segment (CAM regs)
//   addr[8]=1 -> prep_regs segment  (PREP/INJ regs, doc +0x100~0x17C)
ovreg_axil_decode ovreg_axil_decode_u (
    .clk        (axi_clk),
    .rst        (axi_rst),
    .s_awvalid  (ovreg_axil_awvalid),
    .s_awready  (ovreg_axil_awready),
    .s_awaddr   (ovreg_axil_awaddr),
    .s_wvalid   (ovreg_axil_wvalid),
    .s_wready   (ovreg_axil_wready),
    .s_wdata    (ovreg_axil_wdata),
    .s_wstrb    (ovreg_axil_wstrb),
    .s_bvalid   (ovreg_axil_bvalid),
    .s_bready   (ovreg_axil_bready),
    .s_bresp    (ovreg_axil_bresp),
    .s_arvalid  (ovreg_axil_arvalid),
    .s_arready  (ovreg_axil_arready),
    .s_araddr   (ovreg_axil_araddr),
    .s_rvalid   (ovreg_axil_rvalid),
    .s_rready   (ovreg_axil_rready),
    .s_rdata    (ovreg_axil_rdata),
    .s_rresp    (ovreg_axil_rresp),
    .m0_awvalid (cam_axil_awvalid),
    .m0_awready (cam_axil_awready),
    .m0_awaddr  (cam_axil_awaddr),
    .m0_wvalid  (cam_axil_wvalid),
    .m0_wready  (cam_axil_wready),
    .m0_wdata   (cam_axil_wdata),
    .m0_wstrb   (cam_axil_wstrb),
    .m0_bvalid  (cam_axil_bvalid),
    .m0_bready  (cam_axil_bready),
    .m0_bresp   (cam_axil_bresp),
    .m0_arvalid (cam_axil_arvalid),
    .m0_arready (cam_axil_arready),
    .m0_araddr  (cam_axil_araddr),
    .m0_rvalid  (cam_axil_rvalid),
    .m0_rready  (cam_axil_rready),
    .m0_rdata   (cam_axil_rdata),
    .m0_rresp   (cam_axil_rresp),
    .m1_awvalid (prep_axil_awvalid),
    .m1_awready (prep_axil_awready),
    .m1_awaddr  (prep_axil_awaddr),
    .m1_wvalid  (prep_axil_wvalid),
    .m1_wready  (prep_axil_wready),
    .m1_wdata   (prep_axil_wdata),
    .m1_wstrb   (prep_axil_wstrb),
    .m1_bvalid  (prep_axil_bvalid),
    .m1_bready  (prep_axil_bready),
    .m1_bresp   (prep_axil_bresp),
    .m1_arvalid (prep_axil_arvalid),
    .m1_arready (prep_axil_arready),
    .m1_araddr  (prep_axil_araddr),
    .m1_rvalid  (prep_axil_rvalid),
    .m1_rready  (prep_axil_rready),
    .m1_rdata   (prep_axil_rdata),
    .m1_rresp   (prep_axil_rresp),

    .m2_awvalid (cam2_axil_awvalid),
    .m2_awready (cam2_axil_awready),
    .m2_awaddr  (cam2_axil_awaddr),
    .m2_wvalid  (cam2_axil_wvalid),
    .m2_wready  (cam2_axil_wready),
    .m2_wdata   (cam2_axil_wdata),
    .m2_wstrb   (cam2_axil_wstrb),
    .m2_bvalid  (cam2_axil_bvalid),
    .m2_bready  (cam2_axil_bready),
    .m2_bresp   (cam2_axil_bresp),
    .m2_arvalid (cam2_axil_arvalid),
    .m2_arready (cam2_axil_arready),
    .m2_araddr  (cam2_axil_araddr),
    .m2_rvalid  (cam2_axil_rvalid),
    .m2_rready  (cam2_axil_rready),
    .m2_rdata   (cam2_axil_rdata),
    .m2_rresp   (cam2_axil_rresp)
);

// --- prep datapath wiring ---
wire                        prep_bypass_w;
wire [1:0]                  prep_mode_w;
wire [11:0]                 prep_img_width_w;
wire [7:0]                  prep_thr_sat_w, prep_thr_hue_w, prep_thr_val_w, prep_thr_low_w;
wire [10:0]                 prep_thr_edge_w;
wire [7:0]                  prep_lane_roi_top_w, prep_lane_roi_bot_w, prep_lane_row_thr_w, prep_lane_dash_thr_w;
wire [7:0]                  prep_frame_cnt;
wire [15:0]                 inj_addr_w, inj_len_w, inj_fid_w;
wire                        inj_start_w, inj_done_clr_w;
wire [3:0]                  btn_sticky_w, btn_sticky_clr_w, led_ctrl_w;
wire [31:0]                 ts0_w, ts1_w, ts2_w, ts3_w;

// --- PREP/INJ registers (doc +0x100~0x17C). Register stage only: datapath
//     inputs tied to defaults until the preprocess pipeline is integrated.
prep_regs #(.TICK_DIV(50)) prep_regs_u (
    .clk              (axi_clk),
    .rst_n            (~axi_rst),
    .s_axi_awvalid    (prep_axil_awvalid),
    .s_axi_awready    (prep_axil_awready),
    .s_axi_awaddr     (prep_axil_awaddr),
    .s_axi_wvalid     (prep_axil_wvalid),
    .s_axi_wready     (prep_axil_wready),
    .s_axi_wdata      (prep_axil_wdata),
    .s_axi_wstrb      (prep_axil_wstrb),
    .s_axi_bvalid     (prep_axil_bvalid),
    .s_axi_bready     (prep_axil_bready),
    .s_axi_bresp      (prep_axil_bresp),
    .s_axi_arvalid    (prep_axil_arvalid),
    .s_axi_arready    (prep_axil_arready),
    .s_axi_araddr     (prep_axil_araddr),
    .s_axi_rvalid     (prep_axil_rvalid),
    .s_axi_rready     (prep_axil_rready),
    .s_axi_rdata      (prep_axil_rdata),
    .s_axi_rresp      (prep_axil_rresp),
    .prep_bypass      (prep_bypass_w),
    .prep_mode        (prep_mode_w),
    .prep_img_width   (prep_img_width_w),
    .prep_thr_sat     (prep_thr_sat_w),
    .prep_thr_hue     (prep_thr_hue_w),
    .prep_thr_val     (prep_thr_val_w),
    .prep_thr_low     (prep_thr_low_w),
    .prep_thr_edge    (prep_thr_edge_w),
    .prep_lane_roi_top(prep_lane_roi_top_w),
    .prep_lane_roi_bot(prep_lane_roi_bot_w),
    .prep_lane_row_thr(prep_lane_row_thr_w),
    .prep_lane_dash_thr(prep_lane_dash_thr_w),
    .inj_addr         (),
    .inj_len          (),
    .inj_frame_id     (),
    .inj_start        (),
    .inj_done_clr     (),
    .inj_busy         (1'b0),
    .inj_done         (1'b0),
    .inj_done_fid     (16'd0),
    .pipe_frame_sync  (prep_out_frame_start),
    .pipe_fifo_afull  (1'b0),
    .npu_busy         (1'b0),
    .out_frame_cnt    (prep_frame_cnt),
    .btn_toggle_evt   (4'd0),
    .btn_level_sync   (4'd0),
    .btn_sticky       (),
    .btn_sticky_clr   (),
    .led_ctrl         (),
    .lane_left_type   (lane_left_type_w),
    .lane_right_type  (lane_right_type_w),
    .lane_left_valid  (lane_left_valid_w),
    .lane_right_valid (lane_right_valid_w),
    .lane_frame_upd   (lane_frame_upd_w),
    .ts_cap_pulse     (1'b0),
    .ts_prep_pulse    (1'b0),
    .ts_npu_pulse     (1'b0),
    .ts_dma_pulse     (1'b0),
    .ts_value0        (),
    .ts_value1        (),
    .ts_value2        (),
    .ts_value3        ()
);

`ifdef USE_OV5640
ov5640_top #(
    .IODELAY_STEP  (8'd40),
    .MEDIAN_EN     (1'b0)        , // [MEDIAN] cam1/left path only; cam2 remains raw
    .MEDIAN_RSVD   (3'd0)
) ov5640_top(
    .clk_50m       (clk_50m)        ,
    .clk_50m_rst_n (1'b1)                       , //[RSTFIX 2026-09-13] button_rst_n floating-low on this board
    .dbg_locked    (locked)         ,
    .dbg_btn_rst_n (button_rst_n)   ,
    .dbg_axi_awvalid(ov5640_axi_awvalid),
    .dbg_axi_awready(ov5640_axi_awready),
    .dbg_axi_wvalid (ov5640_axi_wvalid ),
    .dbg_axi_wready (ov5640_axi_wready ),
    .dbg_axi_bvalid (ov5640_axi_bvalid ),
    .dbg_axi_bready (ov5640_axi_bready ),
        
    .cam_pclk (cmos1_pclk )             ,  
    .cam_vsync(cmos1_vsync)             ,  
    .cam_href (cmos1_href )             ,  
    .cam_data (cmos1_data )             ,  
    .cam_rst_n(cmos1_rst_n)             ,  
    // .cam_pwdn (cmos1_pwdn )             ,  
    .cam_scl  (cmos1_scl  )             ,  
    .cam_sda  (cmos1_sda  )             ,  


    
    .s_axi_awvalid(cam_axil_awvalid)        ,
    .s_axi_awready(cam_axil_awready)        ,
    .s_axi_awaddr (cam_axil_awaddr )        ,

    .s_axi_wvalid (cam_axil_wvalid)         ,
    .s_axi_wready (cam_axil_wready)         ,
    .s_axi_wdata  (cam_axil_wdata )         ,
    .s_axi_wstrb  (cam_axil_wstrb )         ,

    .s_axi_bvalid (cam_axil_bvalid)         ,
    .s_axi_bready (cam_axil_bready)         ,
    .s_axi_bresp  (cam_axil_bresp )         ,

    .s_axi_arvalid(cam_axil_arvalid)        ,
    .s_axi_arready(cam_axil_arready)        ,
    .s_axi_araddr (cam_axil_araddr )        ,

    .s_axi_rvalid (cam_axil_rvalid )        ,
    .s_axi_rready (cam_axil_rready )        ,
    .s_axi_rdata  (cam_axil_rdata  )        ,
    .s_axi_rresp  (cam_axil_rresp  )        ,



    //AXI_stream
    .video_clk(axi_clk)      ,
    .video_rst(axi_rst)      ,
    .cam_cmd_addr (cam_cmd_addr )  ,
    .cam_cmd_len  (cam_cmd_len  )  ,
    .cam_cmd_valid(cam_cmd_valid)  ,
    .cam_cmd_ready(cam_cmd_ready)  ,

    .cam_s_data      (cam_tap_data      ),
    .cam_s_data_valid(cam_tap_data_valid),
    .cam_s_data_last (cam_tap_data_last ),
    .cam_s_data_ready(cam_tap_data_ready),

    //DMA?
    .cam_dma_done(cam_dma_done),
    .xdma_clk (pcie_clk) ,
    .xdma_irq (cam_irq ) 

);

// [LEDGER 2026-09-19] DMA transaction-done pulses (single beat ledger)
wire cam_dma_done;
wire cam2_dma_done;

// ---- CAM2 (FMC 2nd OV5640, BASE_ADDR 0x2000_0200, 640x480) ----
ov5640_top #(
    .BASE_ADDR       (32'h2000_0200),
    .CAM_ADDR_1_DEF  (32'h00C0_0000),
    .CAM_ADDR_2_DEF  (32'h00E0_0000),
    .CAM_EN_DEF      (1'b1),   // [DUALCAM] keep both camera engines enabled
    .H_CMOS_DISP     (11'd640),
    .V_CMOS_DISP     (11'd480),
    .TOTAL_H_PIXEL   (12'd1896),
    .TOTAL_V_PIXEL   (12'd984)
) cam2_ov5640_top (
    .clk_50m       (clk_50m),
    .clk_50m_rst_n (1'b1),
    .dbg_locked    (locked),
    .dbg_btn_rst_n (button_rst_n),
    .dbg_axi_awvalid(cam2_axi_awvalid),
    .dbg_axi_awready(cam2_axi_awready),
    .dbg_axi_wvalid (cam2_axi_wvalid ),
    .dbg_axi_wready (cam2_axi_wready ),
    .dbg_axi_bvalid (cam2_axi_bvalid ),
    .dbg_axi_bready (cam2_axi_bready ),

    .cam_pclk (cmos2_pclk ),
    .cam_vsync(cmos2_vsync),
    .cam_href (cmos2_href ),
    .cam_data (cmos2_data ),
    .cam_rst_n(cmos2_rst_n),
    .cam_scl  (cmos2_scl  ),
    .cam_sda  (cmos2_sda  ),

    .s_axi_awvalid(cam2_axil_awvalid),
    .s_axi_awready(cam2_axil_awready),
    .s_axi_awaddr (cam2_axil_awaddr ),
    .s_axi_wvalid (cam2_axil_wvalid ),
    .s_axi_wready (cam2_axil_wready ),
    .s_axi_wdata  (cam2_axil_wdata  ),
    .s_axi_wstrb  (cam2_axil_wstrb  ),
    .s_axi_bvalid (cam2_axil_bvalid ),
    .s_axi_bready (cam2_axil_bready ),
    .s_axi_bresp  (cam2_axil_bresp  ),
    .s_axi_arvalid(cam2_axil_arvalid),
    .s_axi_arready(cam2_axil_arready),
    .s_axi_araddr (cam2_axil_araddr ),
    .s_axi_rvalid (cam2_axil_rvalid ),
    .s_axi_rready (cam2_axil_rready ),
    .s_axi_rdata  (cam2_axil_rdata  ),
    .s_axi_rresp  (cam2_axil_rresp  ),

    .video_clk(axi_clk),
    .video_rst(axi_rst),
    .cam_cmd_addr (cam2_cmd_addr ),
    .cam_cmd_len  (cam2_cmd_len  ),
    .cam_cmd_valid(cam2_cmd_valid),
    .cam_cmd_ready(cam2_cmd_ready),

    .cam_s_data      (cam2_s_data      ),
    .cam_s_data_valid(cam2_s_data_valid),
    .cam_s_data_last (cam2_s_data_last ),
    .cam_s_data_ready(cam2_s_data_ready),

    .cam_dma_done(cam2_dma_done),
    .xdma_clk (pcie_clk),
    .xdma_irq (          )
);
`elsif USE_HDMI
hdmi_top hdmi_top(
    .clk_10m(clk_10m)               ,
    .clk_10m_rst_n(locked & button_rst_n)         ,

    //HDMI�ӿ�

    //ms72XX
    .rstn_out(rstn_out),

    // FMC I2C 
    .iic_scl(iic_scl),
    .iic_sda(iic_sda), 

    // .iic_tx_scl(iic_tx_scl),
    // .iic_tx_sda(iic_tx_sda), 

    //HDMI IN
    .pixclk_in(pixclk_in),                            
    .vs_in(vs_in) , 
    .hs_in(hs_in) , 
    .de_in(de_in) ,
    .r_in (r_in ) , 
    .g_in (g_in ) , 
    .b_in (b_in ) ,  




    //����ͷ���ƼĴ���
    .s_axi_awvalid(cam_axil_awvalid)        ,
    .s_axi_awready(cam_axil_awready)        ,
    .s_axi_awaddr (cam_axil_awaddr )        ,

    .s_axi_wvalid (cam_axil_wvalid)         ,
    .s_axi_wready (cam_axil_wready)         ,
    .s_axi_wdata  (cam_axil_wdata )         ,
    .s_axi_wstrb  (cam_axil_wstrb )         ,

    .s_axi_bvalid (cam_axil_bvalid)         ,
    .s_axi_bready (cam_axil_bready)         ,
    .s_axi_bresp  (cam_axil_bresp )         ,

    .s_axi_arvalid(cam_axil_arvalid)        ,
    .s_axi_arready(cam_axil_arready)        ,
    .s_axi_araddr (cam_axil_araddr )        ,

    .s_axi_rvalid (cam_axil_rvalid )        ,
    .s_axi_rready (cam_axil_rready )        ,
    .s_axi_rdata  (cam_axil_rdata  )        ,
    .s_axi_rresp  (cam_axil_rresp  )        ,



    //AXI_stream
    .video_clk(axi_clk)      ,
    .video_rst(axi_rst)      ,
    .cam_cmd_addr (cam_cmd_addr )  ,
    .cam_cmd_len  (cam_cmd_len  )  ,
    .cam_cmd_valid(cam_cmd_valid)  ,
    .cam_cmd_ready(cam_cmd_ready)  ,

    .cam_s_data      (cam_tap_data      ),
    .cam_s_data_valid(cam_tap_data_valid),
    .cam_s_data_last (cam_tap_data_last ),
    .cam_s_data_ready(cam_tap_data_ready),

    //DMA?
    .xdma_clk (pcie_clk) ,
    .xdma_irq (cam_irq ) 

);
`endif

wire [AXI_ID_LEN-1:0]   ov5640_axi_awid    /*synthesis PAP_MARK_DEBUG="1"*/;
wire [31:0]             ov5640_axi_awaddr  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [3:0]              ov5640_axi_awlen   /*synthesis PAP_MARK_DEBUG="1"*/;
wire [2:0]              ov5640_axi_awsize  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [1:0]              ov5640_axi_awburst /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_awlock  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [3:0]              ov5640_axi_awcache /*synthesis PAP_MARK_DEBUG="1"*/;
wire [2:0]              ov5640_axi_awprot  /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_awvalid /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_awready /*synthesis PAP_MARK_DEBUG="1"*/;
wire [AXI_DATA_LEN-1:0] ov5640_axi_wdata   /*synthesis PAP_MARK_DEBUG="1"*/;
wire [AXI_STRB_LEN-1:0] ov5640_axi_wstrb   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_wlast   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_wvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_wready  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [AXI_ID_LEN-1:0]   ov5640_axi_bid     /*synthesis PAP_MARK_DEBUG="1"*/;
wire [1:0]              ov5640_axi_bresp   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_bvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    ov5640_axi_bready  /*synthesis PAP_MARK_DEBUG="1"*/;

axi_dma_write #(
	.BURST_LEN  (BURST_LEN)   ,
	.ID_WIDTH   (AXI_ID_LEN)  ,
	.DATA_WIDTH (AXI_DATA_LEN)
)
ov5640_axi_dma_write(
	.clk(axi_clk)                   ,
	.rst(axi_rst)                   ,

	.cmd_valid (cam_cmd_valid)      ,
	.cmd_addr  (cam_cmd_addr )      ,
	.cmd_len   (cam_cmd_len  )      ,
	.cmd_id    (4'b0001)            ,
	.cmd_ready (cam_cmd_ready)      ,

	.data_in       (cam_s_data          ),
	.data_in_keep  ({AXI_STRB_LEN{1'b1}}),
	.data_in_valid (cam_s_data_valid    ),
	.data_in_last  (cam_dma_done     ),  // [LEDGER 2026-09-19]
	.data_in_ready (cam_s_data_ready    ),

	.m_axi_awid    (ov5640_axi_awid    ),
	.m_axi_awaddr  (ov5640_axi_awaddr  ),
	.m_axi_awlen   (ov5640_axi_awlen   ),
	.m_axi_awsize  (ov5640_axi_awsize  ),
	.m_axi_awburst (ov5640_axi_awburst ),
	.m_axi_awlock  (ov5640_axi_awlock  ),
	.m_axi_awcache (ov5640_axi_awcache ),
	.m_axi_awprot  (ov5640_axi_awprot  ),
	.m_axi_awvalid (ov5640_axi_awvalid ),
	.m_axi_awready (ov5640_axi_awready ),
	.m_axi_wdata   (ov5640_axi_wdata   ),
	.m_axi_wstrb   (ov5640_axi_wstrb   ),
	.m_axi_wlast   (ov5640_axi_wlast   ),
	.m_axi_wvalid  (ov5640_axi_wvalid  ),
	.m_axi_wready  (ov5640_axi_wready  ),
	.m_axi_bid     (ov5640_axi_bid     ),
	.m_axi_bresp   (ov5640_axi_bresp   ),
	.m_axi_bvalid  (ov5640_axi_bvalid  ),
	.m_axi_bready  (ov5640_axi_bready  )
);

axi_dma_write #(
	.BURST_LEN  (BURST_LEN)   ,
	.ID_WIDTH   (AXI_ID_LEN)  ,
	.DATA_WIDTH (AXI_DATA_LEN)
)
cam2_axi_dma_write(
	.clk(axi_clk)                   ,
	.rst(axi_rst)                   ,

	.cmd_valid (cam2_cmd_valid)     ,
	.cmd_addr  (cam2_cmd_addr )     ,
	.cmd_len   (cam2_cmd_len  )     ,
	.cmd_id    (4'b0100)            ,
	.cmd_ready (cam2_cmd_ready)     ,

	.data_in       (cam2_s_data          ),
	.data_in_keep  ({AXI_STRB_LEN{1'b1}}),
	.data_in_valid (cam2_s_data_valid    ),
	.data_in_last  (cam2_dma_done    ),  // [LEDGER 2026-09-19]
	.data_in_ready (cam2_s_data_ready    ),

	.m_axi_awid    (cam2_axi_awid    ),
	.m_axi_awaddr  (cam2_axi_awaddr  ),
	.m_axi_awlen   (cam2_axi_awlen   ),
	.m_axi_awsize  (cam2_axi_awsize  ),
	.m_axi_awburst (cam2_axi_awburst ),
	.m_axi_awlock  (cam2_axi_awlock  ),
	.m_axi_awcache (cam2_axi_awcache ),
	.m_axi_awprot  (cam2_axi_awprot  ),
	.m_axi_awvalid (cam2_axi_awvalid ),
	.m_axi_awready (cam2_axi_awready ),
	.m_axi_wdata   (cam2_axi_wdata   ),
	.m_axi_wstrb   (cam2_axi_wstrb   ),
	.m_axi_wlast   (cam2_axi_wlast   ),
	.m_axi_wvalid  (cam2_axi_wvalid  ),
	.m_axi_wready  (cam2_axi_wready  ),
	.m_axi_bid     (cam2_axi_bid     ),
	.m_axi_bresp   (cam2_axi_bresp   ),
	.m_axi_bvalid  (cam2_axi_bvalid  ),
	.m_axi_bready  (cam2_axi_bready  )
);
// ===================== preprocess datapath (PREP, batch-2) =====================
reg [7:0] prep_frame_cnt;
always @(posedge axi_clk) begin
    if (axi_rst)
        prep_frame_cnt <= 8'd0;
    else if (prep_out_frame_start)
        prep_frame_cnt <= prep_frame_cnt + 8'd1;
end
// camera raw stream -> cam_prep_link (tap) -> preprocess_top -> processed
// write engine (second axi_dma_write, crossbar S03 write channel)
wire [AXI_DATA_LEN-1:0] prep_wr_data;
wire                    prep_wr_valid;
wire                    prep_wr_ready;
wire                    prep_wr_cmd_valid;
wire                    prep_wr_cmd_ready;
wire [31:0]             prep_wr_cmd_addr;
wire [31:0]             prep_wr_cmd_len;
wire [15:0]             prep_pp_data;
wire                    prep_pp_valid;
wire                    prep_pp_ready;
wire                    prep_pp_fsync;
wire [15:0]             prep_out_data;
wire                    prep_out_valid;
wire                    prep_out_ready;
wire                    prep_out_fsync;
wire                    prep_out_frame_start;
wire                    prep_edge_valid;
wire                    prep_edge_bit;
wire [7:0]              prep_edge_center;
wire                    prep_cid_valid;
wire [1:0]              prep_cid;
wire [1:0]              lane_left_type_w, lane_right_type_w;
wire                    lane_left_valid_w, lane_right_valid_w, lane_frame_upd_w;

// [OptionB 2026-09-12] WIP pixel-path disabled: recover 53006-reg verified netlist (DOC v1.1 3.3). Phase-2: recalibrate cam_prep_link TB then restore.
// cam_prep_link #(
//     .FRAME_H (720),
//     .BUFFER0 (32'h0A00_0000),
//     .BUFFER1 (32'h0A1C_2000)
// ) cam_prep_link_u (
//     .clk            (axi_clk),
//     .rst            (axi_rst),
//     .img_width      (prep_img_width_w),
//     .bypass_mode    (prep_bypass_w),
//     .mode           (prep_mode_w),
//     .cam_data       (cam_tap_data),
//     .cam_valid      (cam_tap_data_valid),
//     .cam_ready      (cam_tap_data_ready),
//     .cam_frame_sync (cam_cmd_valid),
//     .raw_data       (cam_s_data),
//     .raw_valid      (cam_s_data_valid),
//     .raw_ready      (cam_s_data_ready),
//     .pp_data        (prep_pp_data),
//     .pp_valid       (prep_pp_valid),
//     .pp_ready       (prep_pp_ready),
//     .pp_frame_sync  (prep_pp_fsync),
//     .out_data       (prep_out_data),
//     .out_valid      (prep_out_valid),
//     .out_ready      (prep_out_ready),
//     .out_frame_sync (prep_out_fsync),
//     .wr_cmd_valid   (prep_wr_cmd_valid),
//     .wr_cmd_ready   (prep_wr_cmd_ready),
//     .wr_cmd_addr    (prep_wr_cmd_addr),
//     .wr_cmd_len     (prep_wr_cmd_len),
//     .wr_data        (prep_wr_data),
//     .wr_valid       (prep_wr_valid),
//     .wr_ready       (prep_wr_ready)
// );

// [OptionB 2026-09-12] WIP pixel-path disabled: recover 53006-reg verified netlist (DOC v1.1 3.3). Phase-2: recalibrate cam_prep_link TB then restore.
// preprocess_top #(
//     .MAX_WIDTH   (1920),
//     .FIFO_DEPTH  (512)
// ) preprocess_top_u (
//     .clk            (axi_clk),
//     .rst_n          (~axi_rst),
//     .s_rgb565       (prep_pp_data),
//     .s_valid        (prep_pp_valid),
//     .s_ready        (prep_pp_ready),
//     .s_frame_sync   (prep_pp_fsync),
//     .m_ready        (prep_out_ready),
//     .m_rgb565       (prep_out_data),
//     .m_valid        (prep_out_valid),
//     .m_frame_sync   (prep_out_fsync),
//     .reg_bypass     (prep_bypass_w),
//     .reg_mode       (prep_mode_w),
//     .reg_img_width  (prep_img_width_w),
//     .reg_thr_sat    (prep_thr_sat_w),
//     .reg_thr_hue    (prep_thr_hue_w),
//     .reg_thr_val    (prep_thr_val_w),
//     .reg_thr_low    (prep_thr_low_w),
//     .reg_thr_edge   (prep_thr_edge_w),
//     .out_frame_start(prep_out_frame_start),
//     .edge_stream_valid (prep_edge_valid),
//     .edge_stream_edge  (prep_edge_bit),
//     .edge_stream_center(prep_edge_center),
//     .color_id_valid (prep_cid_valid),
//     .color_id       (prep_cid)
// );

// [OptionB 2026-09-12] WIP pixel-path disabled: recover 53006-reg verified netlist (DOC v1.1 3.3). Phase-2: recalibrate cam_prep_link TB then restore.
// lane_detect #(
//     .MAX_WIDTH(1920)
// ) lane_detect_u (
//     .clk        (axi_clk),
//     .rst_n      (~axi_rst),
//     .img_width  (prep_img_width_w),
//     .img_height (12'd720),
//     .roi_top_pct(prep_lane_roi_top_w),
//     .roi_bot_pct(prep_lane_roi_bot_w),
//     .row_thr    (prep_lane_row_thr_w),
//     .dash_thr   (prep_lane_dash_thr_w),
//     .s_center   (prep_edge_center),
//     .s_edge     (prep_edge_bit),
//     .s_valid    (prep_edge_valid),
//     .s_frame_sync(prep_out_frame_start),
//     .m_left_type (lane_left_type_w),
//     .m_right_type(lane_right_type_w),
//     .m_left_valid (lane_left_valid_w),
//     .m_right_valid(lane_right_valid_w),
//     .m_frame_upd  (lane_frame_upd_w)
// );


// ===== [2026-09-12] RAW camera path restored =====
// OptionB commented out cam_prep_link but left cam_s_data undriven, so the
// camera never wrote DDR -> no frames / no MSI. ov5640_top already emits a
// complete raw AXI-stream write request, so wire it straight to the raw write
// engine. The preprocess tap is intentionally NOT used (its TB still fails and
// its dummy-inject can back-pressure/stall the camera).
assign cam_s_data         = cam_tap_data;
assign cam_s_data_valid   = cam_tap_data_valid;
assign cam_s_data_last    = cam_tap_data_last;
assign cam_tap_data_ready = cam_s_data_ready;

// preprocess datapath disabled: keep the processed-frame write engine idle
assign prep_wr_cmd_valid = 1'b0;
assign prep_wr_cmd_addr  = 32'b0;
assign prep_wr_cmd_len   = 32'b0;
assign prep_wr_data      = 128'b0;
assign prep_wr_valid     = 1'b0;

// processed-frame write engine (second write master -> crossbar S03 AW/W/B)
wire [AXI_ID_LEN-1:0]   prep2_axi_awid;
wire [31:0]             prep2_axi_awaddr;
wire [3:0]              prep2_axi_awlen;
wire [2:0]              prep2_axi_awsize;
wire [1:0]              prep2_axi_awburst;
wire                    prep2_axi_awlock;
wire [3:0]              prep2_axi_awcache;
wire [2:0]              prep2_axi_awprot;
wire                    prep2_axi_awvalid;
wire                    prep2_axi_awready;
wire [AXI_DATA_LEN-1:0] prep2_axi_wdata;
wire [AXI_STRB_LEN-1:0] prep2_axi_wstrb;
wire                    prep2_axi_wlast;
wire                    prep2_axi_wvalid;
wire                    prep2_axi_wready;
wire [AXI_ID_LEN-1:0]   prep2_axi_bid;
wire [1:0]              prep2_axi_bresp;
wire                    prep2_axi_bvalid;
wire                    prep2_axi_bready;

axi_dma_write #(
    .BURST_LEN  (BURST_LEN),
    .ID_WIDTH   (AXI_ID_LEN),
    .DATA_WIDTH (AXI_DATA_LEN)
) prep_axi_dma_write(
    .clk(axi_clk),
    .rst(axi_rst),
    .cmd_valid (prep_wr_cmd_valid),
    .cmd_addr  (prep_wr_cmd_addr),
    .cmd_len   (prep_wr_cmd_len),
    .cmd_id    (4'b0111),
    .cmd_ready (prep_wr_cmd_ready),
    .data_in       (prep_wr_data),
    .data_in_keep  ({AXI_STRB_LEN{1'b1}}),
    .data_in_valid (prep_wr_valid),
    .data_in_last  (),
    .data_in_ready (prep_wr_ready),
    .m_axi_awid    (prep2_axi_awid),
    .m_axi_awaddr  (prep2_axi_awaddr),
    .m_axi_awlen   (prep2_axi_awlen),
    .m_axi_awsize  (prep2_axi_awsize),
    .m_axi_awburst (prep2_axi_awburst),
    .m_axi_awlock  (prep2_axi_awlock),
    .m_axi_awcache (prep2_axi_awcache),
    .m_axi_awprot  (prep2_axi_awprot),
    .m_axi_awvalid (prep2_axi_awvalid),
    .m_axi_awready (prep2_axi_awready),
    .m_axi_wdata   (prep2_axi_wdata),
    .m_axi_wstrb   (prep2_axi_wstrb),
    .m_axi_wlast   (prep2_axi_wlast),
    .m_axi_wvalid  (prep2_axi_wvalid),
    .m_axi_wready  (prep2_axi_wready),
    .m_axi_bid     (prep2_axi_bid),
    .m_axi_bresp   (prep2_axi_bresp),
    .m_axi_bvalid  (prep2_axi_bvalid),
    .m_axi_bready  (prep2_axi_bready)
);
// =================== preprocess datapath end ===================


/////////////////////////////////////////////////////////////////////////////////////////////
wire [AXI_ID_LEN-1:0]   npu_reg_axi_awid    /*synthesis PAP_MARK_DEBUG="1"*/;
wire [31:0]             npu_reg_axi_awaddr  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [3:0]              npu_reg_axi_awlen   /*synthesis PAP_MARK_DEBUG="1"*/;
wire [2:0]              npu_reg_axi_awsize  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [1:0]              npu_reg_axi_awburst /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_awlock  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [3:0]              npu_reg_axi_awcache /*synthesis PAP_MARK_DEBUG="1"*/;
wire [2:0]              npu_reg_axi_awprot  /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_awvalid /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_awready /*synthesis PAP_MARK_DEBUG="1"*/;
wire [AXI_DATA_LEN-1:0] npu_reg_axi_wdata   /*synthesis PAP_MARK_DEBUG="1"*/;
wire [AXI_STRB_LEN-1:0] npu_reg_axi_wstrb   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_wlast   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_wvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_wready  /*synthesis PAP_MARK_DEBUG="1"*/;
wire [AXI_ID_LEN-1:0]   npu_reg_axi_bid     /*synthesis PAP_MARK_DEBUG="1"*/;
wire [1:0]              npu_reg_axi_bresp   /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_bvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
wire                    npu_reg_axi_bready  /*synthesis PAP_MARK_DEBUG="1"*/;






    








    wire [AXI_ID_LEN-1:0]   npu_out_axi_awid    /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [31:0]             npu_out_axi_awaddr  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [3:0]              npu_out_axi_awlen   /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [2:0]              npu_out_axi_awsize  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [1:0]              npu_out_axi_awburst /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_awlock  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [3:0]              npu_out_axi_awcache /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [2:0]              npu_out_axi_awprot  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_awvalid /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_awready /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [AXI_DATA_LEN-1:0] npu_out_axi_wdata   /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [AXI_STRB_LEN-1:0] npu_out_axi_wstrb   /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_wlast   /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_wvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_wready  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [AXI_ID_LEN-1:0]   npu_out_axi_bid     /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [1:0]              npu_out_axi_bresp   /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_bvalid  /*synthesis PAP_MARK_DEBUG="1"*/;
    wire                    npu_out_axi_bready  /*synthesis PAP_MARK_DEBUG="1"*/;


    wire    [AXI_ID_LEN-1:0]    npu_s0_axi_arid    ;
    wire    [31:0]              npu_s0_axi_araddr  ;
    wire    [3:0]               npu_s0_axi_arlen   ;
    wire    [2:0]               npu_s0_axi_arsize  ;
    wire    [1:0]               npu_s0_axi_arburst ;
    wire                        npu_s0_axi_arlock  ;
    wire    [3:0]               npu_s0_axi_arcache ;
    wire    [2:0]               npu_s0_axi_arprot  ;
    wire                        npu_s0_axi_arvalid ;
    wire                        npu_s0_axi_arready ;
    wire    [AXI_ID_LEN-1:0]    npu_s0_axi_rid     ;
    wire    [AXI_DATA_LEN-1:0]  npu_s0_axi_rdata   ;
    wire    [1:0]               npu_s0_axi_rresp   ;
    wire                        npu_s0_axi_rlast   ;
    wire                        npu_s0_axi_rvalid  ;
    wire                        npu_s0_axi_rready  ;


    wire    [AXI_ID_LEN-1:0]    npu_s1_axi_arid    ;
    wire    [31:0]              npu_s1_axi_araddr  ;
    wire    [3:0]               npu_s1_axi_arlen   ;
    wire    [2:0]               npu_s1_axi_arsize  ;
    wire    [1:0]               npu_s1_axi_arburst ;
    wire                        npu_s1_axi_arlock  ;
    wire    [3:0]               npu_s1_axi_arcache ;
    wire    [2:0]               npu_s1_axi_arprot  ;
    wire                        npu_s1_axi_arvalid ;
    wire                        npu_s1_axi_arready ;
    wire    [AXI_ID_LEN-1:0]    npu_s1_axi_rid     ;
    wire    [AXI_DATA_LEN-1:0]  npu_s1_axi_rdata   ;
    wire    [1:0]               npu_s1_axi_rresp   ;
    wire                        npu_s1_axi_rlast   ;
    wire                        npu_s1_axi_rvalid  ;
    wire                        npu_s1_axi_rready  ;






    wire    [AXI_ID_LEN-1:0]    npu_s2_axi_arid    ;
    wire    [31:0]              npu_s2_axi_araddr  ;
    wire    [3:0]               npu_s2_axi_arlen   ;
    wire    [2:0]               npu_s2_axi_arsize  ;
    wire    [1:0]               npu_s2_axi_arburst ;
    wire                        npu_s2_axi_arlock  ;
    wire    [3:0]               npu_s2_axi_arcache ;
    wire    [2:0]               npu_s2_axi_arprot  ;
    wire                        npu_s2_axi_arvalid ;
    wire                        npu_s2_axi_arready ;
    wire    [AXI_ID_LEN-1:0]    npu_s2_axi_rid     ;
    wire    [AXI_DATA_LEN-1:0]  npu_s2_axi_rdata   ;
    wire    [1:0]               npu_s2_axi_rresp   ;
    wire                        npu_s2_axi_rlast   ;
    wire                        npu_s2_axi_rvalid  ;
    wire                        npu_s2_axi_rready  ;






    wire    [AXI_ID_LEN-1:0]    npu_s3_axi_arid    ;
    wire    [31:0]              npu_s3_axi_araddr  ;
    wire    [3:0]               npu_s3_axi_arlen   ;
    wire    [2:0]               npu_s3_axi_arsize  ;
    wire    [1:0]               npu_s3_axi_arburst ;
    wire                        npu_s3_axi_arlock  ;
    wire    [3:0]               npu_s3_axi_arcache ;
    wire    [2:0]               npu_s3_axi_arprot  ;
    wire                        npu_s3_axi_arvalid ;
    wire                        npu_s3_axi_arready ;
    wire    [AXI_ID_LEN-1:0]    npu_s3_axi_rid     ;
    wire    [AXI_DATA_LEN-1:0]  npu_s3_axi_rdata   ;
    wire    [1:0]               npu_s3_axi_rresp   ;
    wire                        npu_s3_axi_rlast   ;
    wire                        npu_s3_axi_rvalid  ;
    wire                        npu_s3_axi_rready  ;






    wire    [AXI_ID_LEN-1:0]    npu_s4_axi_arid    ;
    wire    [31:0]              npu_s4_axi_araddr  ;
    wire    [3:0]               npu_s4_axi_arlen   ;
    wire    [2:0]               npu_s4_axi_arsize  ;
    wire    [1:0]               npu_s4_axi_arburst ;
    wire                        npu_s4_axi_arlock  ;
    wire    [3:0]               npu_s4_axi_arcache ;
    wire    [2:0]               npu_s4_axi_arprot  ;
    wire                        npu_s4_axi_arvalid ;
    wire                        npu_s4_axi_arready ;
    wire    [AXI_ID_LEN-1:0]    npu_s4_axi_rid     ;
    wire    [AXI_DATA_LEN-1:0]  npu_s4_axi_rdata   ;
    wire    [1:0]               npu_s4_axi_rresp   ;
    wire                        npu_s4_axi_rlast   ;
    wire                        npu_s4_axi_rvalid  ;
    wire                        npu_s4_axi_rready  ;


// ===== NPU removed: tie off crossbar-facing NPU ports =====
// S02 write (npu_out) + S02 read (npu_s0)
assign npu_out_axi_awvalid = 1'b0;
assign npu_out_axi_wvalid  = 1'b0;
assign npu_out_axi_bready  = 1'b1;
assign npu_s0_axi_arvalid  = 1'b0;
assign npu_s0_axi_rready   = 1'b1;
// S03 read (npu_s1) ; S03 write (prep2) stays active
assign npu_s1_axi_arvalid  = 1'b0;
assign npu_s1_axi_rready   = 1'b1;
// S04/S05/S06 read (npu_s2/s3/s4)
assign npu_s2_axi_arvalid  = 1'b0;
assign npu_s2_axi_rready   = 1'b1;
assign npu_s3_axi_arvalid  = 1'b0;
assign npu_s3_axi_rready   = 1'b1;
assign npu_s4_axi_arvalid  = 1'b0;
assign npu_s4_axi_rready   = 1'b1;
// M02 (NPU register window) response inputs
assign npu_reg_axi_awready = 1'b1;
assign npu_reg_axi_wready  = 1'b1;
assign npu_reg_axi_bid     = {AXI_ID_LEN{1'b0}};
assign npu_reg_axi_bresp   = 2'b00;
assign npu_reg_axi_bvalid  = 1'b0;
wire   [AXI_ID_LEN-1:0]   npu_reg_axi_rid;
wire   [AXI_DATA_LEN-1:0] npu_reg_axi_rdata;
wire   [1:0]              npu_reg_axi_rresp;
wire                      npu_reg_axi_rlast;
wire                      npu_reg_axi_rvalid;
wire                      npu_reg_axi_arready;
assign npu_reg_axi_arready = 1'b1;
assign npu_reg_axi_rid     = {AXI_ID_LEN{1'b0}};
assign npu_reg_axi_rdata   = {AXI_DATA_LEN{1'b0}};
assign npu_reg_axi_rresp   = 2'b00;
assign npu_reg_axi_rlast   = 1'b0;
assign npu_reg_axi_rvalid  = 1'b0;

///////////////////////////////////////////////////////////////////////////////////////////
axi_crossbar_7x3 #(
    //.DATA_WIDTH(AXI_DATA_LEN)
    .DATA_WIDTH(AXI_DATA_LEN),
    // M00 (DDR3) �ķ���Ȩ�ޣ�
    // �� DDR: ���� PCIE(S00) �� NPU����ͨ��(S02-S06)����ֹ Camera(S01)
    .M00_CONNECT_READ  (7'b1111101), 
    // д DDR: ���� PCIE(S00), Camera(S01), NPU_S0(S02)����ֹ NPU_S1~S4(S03-S06)
    .M00_CONNECT_WRITE (7'b0000000),  // [WARB 2026-09-19] write path moved to ddr_w_arb
                                      // (crossbar M00 write leaked its W-channel select
                                      //  across handoffs -> permanent wedge; bench-proven)
    
    // M01 (OV5640 ���ƼĴ���) �ķ���Ȩ�ޣ�
    // ֻ�� PCIE (S00) ���Զ�д�������ж���������ͨ���ĸ���
    .M01_CONNECT_READ  (7'b0000001),
    .M01_CONNECT_WRITE (7'b0000001),
    
    // M02 (NPU ���ƼĴ���) �ķ���Ȩ�ޣ�
    // ֻ�� PCIE (S00) ���Զ�д
    .M02_CONNECT_READ  (7'b0000001),
    .M02_CONNECT_WRITE (7'b0000001)
)
axi_crossbar_7x3
(
    .clk(axi_clk),
    .rst(axi_rst),

    /*
     * AXI slave interface
     */
    .s00_axi_awid   (pcie_axi_awid   ) ,
    .s00_axi_awaddr (pcie_axi_awaddr ) ,
    .s00_axi_awlen  (pcie_axi_awlen  ) ,
    .s00_axi_awsize (pcie_axi_awsize ) ,
    .s00_axi_awburst(pcie_axi_awburst) ,
    .s00_axi_awlock (pcie_axi_awlock ) ,
    .s00_axi_awcache(pcie_axi_awcache) ,
    .s00_axi_awprot (pcie_axi_awprot ) ,
    .s00_axi_awqos  (pcie_axi_awqos  ) ,
    .s00_axi_awvalid(pcie_axi_awvalid) ,
    .s00_axi_awready(pcie_axi_awready) ,
    .s00_axi_awuser () ,

    .s00_axi_wdata  (pcie_axi_wdata  ) ,
    .s00_axi_wstrb  (pcie_axi_wstrb  ) ,
    .s00_axi_wlast  (pcie_axi_wlast  ) ,
    .s00_axi_wready (pcie_axi_wready ) ,
    .s00_axi_wvalid (pcie_axi_wvalid ) ,
    .s00_axi_wuser  () ,

    .s00_axi_bid     (pcie_axi_bid   ),   
    .s00_axi_bresp   (pcie_axi_bresp ),
    .s00_axi_bvalid  (pcie_axi_bvalid),
    .s00_axi_bready  (pcie_axi_bready),
    .s00_axi_buser   (),

    .s00_axi_arid    (pcie_axi_arid   )     ,
    .s00_axi_araddr  (pcie_axi_araddr )     ,
    .s00_axi_arlen   (pcie_axi_arlen  )     ,
    .s00_axi_arsize  (pcie_axi_arsize )     ,
    .s00_axi_arburst (pcie_axi_arburst)     ,
    .s00_axi_arlock  (pcie_axi_arlock )     ,
    .s00_axi_arcache (pcie_axi_arcache)     ,
    .s00_axi_arprot  (pcie_axi_arprot )     ,
    .s00_axi_arqos   (pcie_axi_arqos  )     ,
    .s00_axi_arvalid (pcie_axi_arvalid)     ,
    .s00_axi_arready (pcie_axi_arready)     ,
    .s00_axi_aruser  (),

    .s00_axi_rid     (pcie_axi_rid    ),
    .s00_axi_rdata   (pcie_axi_rdata  ),
    .s00_axi_rresp   (pcie_axi_rresp  ),
    .s00_axi_rlast   (pcie_axi_rlast  ),
    .s00_axi_rvalid  (pcie_axi_rvalid ),
    .s00_axi_rready  (pcie_axi_rready ),
    .s00_axi_ruser   (),

    // [WARB] S01 write retired (camera DMAs go through ddr_w_arb)
    .s01_axi_awid    (4'd0               ),
    .s01_axi_awaddr  (32'd0              ),
    .s01_axi_awlen   (8'd0               ),
    .s01_axi_awsize  (3'd0               ),
    .s01_axi_awburst (2'd0               ),
    .s01_axi_awlock  (1'b0               ),
    .s01_axi_awcache (4'd0               ),
    .s01_axi_awprot  (3'd0               ),
    .s01_axi_awqos   (4'd0               ),
    .s01_axi_awvalid (1'b0               ),
    .s01_axi_awready (               ),
    .s01_axi_awuser  (               ),
    .s01_axi_wdata   (128'd0             ),
    .s01_axi_wstrb   (16'd0              ),
    .s01_axi_wlast   (1'b0               ),
    .s01_axi_wvalid  (1'b0               ),
    .s01_axi_wready  (               ),
    .s01_axi_wuser   (               ),
    .s01_axi_bid     (               ),
    .s01_axi_bresp   (               ),
    .s01_axi_bvalid  (               ),
    .s01_axi_bready  (1'b0               ),
    .s01_axi_buser   (               ),
    .s01_axi_arid    (4'd0               ),
    .s01_axi_araddr  (32'd0              ),
    .s01_axi_arlen   (8'd0               ),
    .s01_axi_arsize  (3'd0               ),
    .s01_axi_arburst (2'd0               ),
    .s01_axi_arlock  (1'b0               ),
    .s01_axi_arcache (4'd0               ),
    .s01_axi_arprot  (3'd0               ),
    .s01_axi_arqos   (4'd0               ),
    .s01_axi_aruser  (1'b0               ),
    .s01_axi_arvalid (1'b0               ),
    .s01_axi_arready (),
    .s01_axi_rid     (),
    .s01_axi_rdata   (),
    .s01_axi_rresp   (),
    .s01_axi_rlast   (),
    .s01_axi_ruser   (),
    .s01_axi_rvalid  (),
    .s01_axi_rready  (1'b0               ),

    .s02_axi_awid   (npu_out_axi_awid   ),
    .s02_axi_awaddr (npu_out_axi_awaddr ),
    .s02_axi_awlen  (npu_out_axi_awlen  ),
    .s02_axi_awsize (npu_out_axi_awsize ),
    .s02_axi_awburst(npu_out_axi_awburst),
    .s02_axi_awlock (npu_out_axi_awlock ),
    .s02_axi_awcache(npu_out_axi_awcache),
    .s02_axi_awprot (npu_out_axi_awprot ),
    .s02_axi_awqos  (4'd0),
    .s02_axi_awuser (),
    .s02_axi_awvalid(npu_out_axi_awvalid),
    .s02_axi_awready(npu_out_axi_awready),
    .s02_axi_wdata  (npu_out_axi_wdata  ),
    .s02_axi_wstrb  (npu_out_axi_wstrb  ),
    .s02_axi_wlast  (npu_out_axi_wlast  ),
    .s02_axi_wvalid (npu_out_axi_wvalid ),
    .s02_axi_wready (npu_out_axi_wready ),
    .s02_axi_wuser  (),
    .s02_axi_bid    (npu_out_axi_bid    ),
    .s02_axi_bresp  (npu_out_axi_bresp  ),
    .s02_axi_bvalid (npu_out_axi_bvalid ),
    .s02_axi_bready (npu_out_axi_bready ),
    .s02_axi_buser  (),

    .s02_axi_arid   (npu_s0_axi_arid    ),
    .s02_axi_araddr (npu_s0_axi_araddr  ),
    .s02_axi_arlen  (npu_s0_axi_arlen   ),
    .s02_axi_arsize (npu_s0_axi_arsize  ),
    .s02_axi_arburst(npu_s0_axi_arburst ),
    .s02_axi_arlock (npu_s0_axi_arlock  ),
    .s02_axi_arcache(npu_s0_axi_arcache ),
    .s02_axi_arprot (npu_s0_axi_arprot  ),
    .s02_axi_arqos  (4'd0),
    .s02_axi_aruser (),
    .s02_axi_arvalid(npu_s0_axi_arvalid ),
    .s02_axi_arready(npu_s0_axi_arready ),
    .s02_axi_rid    (npu_s0_axi_rid     ),
    .s02_axi_rdata  (npu_s0_axi_rdata   ),
    .s02_axi_rresp  (npu_s0_axi_rresp   ),
    .s02_axi_rlast  (npu_s0_axi_rlast   ),
    .s02_axi_rvalid (npu_s0_axi_rvalid  ),
    .s02_axi_rready (npu_s0_axi_rready  ),
    .s02_axi_ruser  (),

    .s03_axi_awid   (prep2_axi_awid   ),
    .s03_axi_awaddr (prep2_axi_awaddr ),
    .s03_axi_awlen  (prep2_axi_awlen  ),
    .s03_axi_awsize (prep2_axi_awsize ),
    .s03_axi_awburst(prep2_axi_awburst),
    .s03_axi_awlock (prep2_axi_awlock ),
    .s03_axi_awcache(prep2_axi_awcache),
    .s03_axi_awprot (prep2_axi_awprot ),
    .s03_axi_awqos  (4'd0),
    .s03_axi_awuser (),
    .s03_axi_awvalid(prep2_axi_awvalid),
    .s03_axi_awready(prep2_axi_awready),
    .s03_axi_wdata  (prep2_axi_wdata ),
    .s03_axi_wstrb  (prep2_axi_wstrb ),
    .s03_axi_wlast  (prep2_axi_wlast ),
    .s03_axi_wuser  (),
    .s03_axi_wvalid (prep2_axi_wvalid),
    .s03_axi_wready (prep2_axi_wready),
    .s03_axi_bid    (prep2_axi_bid   ),
    .s03_axi_bresp  (prep2_axi_bresp ),
    .s03_axi_buser  (),
    .s03_axi_bvalid (prep2_axi_bvalid),
    .s03_axi_bready (prep2_axi_bready),
    .s03_axi_arid   (npu_s1_axi_arid    ),
    .s03_axi_araddr (npu_s1_axi_araddr  ),
    .s03_axi_arlen  (npu_s1_axi_arlen   ),
    .s03_axi_arsize (npu_s1_axi_arsize  ),
    .s03_axi_arburst(npu_s1_axi_arburst ),
    .s03_axi_arlock (npu_s1_axi_arlock  ),
    .s03_axi_arcache(npu_s1_axi_arcache ),
    .s03_axi_arprot (npu_s1_axi_arprot  ),
    .s03_axi_arqos  (4'd0),
    .s03_axi_aruser (),
    .s03_axi_arvalid(npu_s1_axi_arvalid ),
    .s03_axi_arready(npu_s1_axi_arready ),
    .s03_axi_rid    (npu_s1_axi_rid     ),
    .s03_axi_rdata  (npu_s1_axi_rdata   ),
    .s03_axi_rresp  (npu_s1_axi_rresp   ),
    .s03_axi_rlast  (npu_s1_axi_rlast   ),
    .s03_axi_rvalid (npu_s1_axi_rvalid  ),
    .s03_axi_rready (npu_s1_axi_rready  ),
    .s03_axi_ruser  (),

    // [WARB] S04 write retired (cam2 DMA goes through ddr_w_arb)
    .s04_axi_awid   (4'd0            ),
    .s04_axi_awaddr (32'd0           ),
    .s04_axi_awlen  (8'd0            ),
    .s04_axi_awsize (3'd0            ),
    .s04_axi_awburst(2'd0            ),
    .s04_axi_awlock (1'b0            ),
    .s04_axi_awcache(4'd0            ),
    .s04_axi_awprot (3'd0            ),
    .s04_axi_awqos  (4'd0),
    .s04_axi_awuser (),
    .s04_axi_awvalid(1'b0            ),
    .s04_axi_awready(                ),
    .s04_axi_wdata  (128'd0          ),
    .s04_axi_wstrb  (16'd0           ),
    .s04_axi_wlast  (1'b0            ),
    .s04_axi_wuser  (),
    .s04_axi_wvalid (1'b0            ),
    .s04_axi_wready (                ),
    .s04_axi_bid    (                ),
    .s04_axi_bresp  (                ),
    .s04_axi_buser  (),
    .s04_axi_bvalid (                ),
    .s04_axi_bready (1'b0            ),
    .s04_axi_arid   (npu_s2_axi_arid    ),
    .s04_axi_araddr (npu_s2_axi_araddr  ),
    .s04_axi_arlen  (npu_s2_axi_arlen   ),
    .s04_axi_arsize (npu_s2_axi_arsize  ),
    .s04_axi_arburst(npu_s2_axi_arburst ),
    .s04_axi_arlock (npu_s2_axi_arlock  ),
    .s04_axi_arcache(npu_s2_axi_arcache ),
    .s04_axi_arprot (npu_s2_axi_arprot  ),
    .s04_axi_arqos  (4'd0),
    .s04_axi_aruser (),
    .s04_axi_arvalid(npu_s2_axi_arvalid ),
    .s04_axi_arready(npu_s2_axi_arready ),
    .s04_axi_rid    (npu_s2_axi_rid     ),
    .s04_axi_rdata  (npu_s2_axi_rdata   ),
    .s04_axi_rresp  (npu_s2_axi_rresp   ),
    .s04_axi_rlast  (npu_s2_axi_rlast   ),
    .s04_axi_rvalid (npu_s2_axi_rvalid  ),
    .s04_axi_rready (npu_s2_axi_rready  ),
    .s04_axi_ruser  (),

    .s05_axi_awid(),
    .s05_axi_awaddr(),
    .s05_axi_awlen(),
    .s05_axi_awsize(),
    .s05_axi_awburst(),
    .s05_axi_awlock(),
    .s05_axi_awcache(),
    .s05_axi_awprot(),
    .s05_axi_awqos(),
    .s05_axi_awuser(),
    .s05_axi_awvalid(),
    .s05_axi_awready(),
    .s05_axi_wdata(),
    .s05_axi_wstrb(),
    .s05_axi_wlast(),
    .s05_axi_wuser(),
    .s05_axi_wvalid(),
    .s05_axi_wready(),
    .s05_axi_bid(),
    .s05_axi_bresp(),
    .s05_axi_buser(),
    .s05_axi_bvalid(),
    .s05_axi_bready(),
    .s05_axi_arid   (npu_s3_axi_arid    ),
    .s05_axi_araddr (npu_s3_axi_araddr  ),
    .s05_axi_arlen  (npu_s3_axi_arlen   ),
    .s05_axi_arsize (npu_s3_axi_arsize  ),
    .s05_axi_arburst(npu_s3_axi_arburst ),
    .s05_axi_arlock (npu_s3_axi_arlock  ),
    .s05_axi_arcache(npu_s3_axi_arcache ),
    .s05_axi_arprot (npu_s3_axi_arprot  ),
    .s05_axi_arqos  (4'd0),
    .s05_axi_aruser (),
    .s05_axi_arvalid(npu_s3_axi_arvalid ),
    .s05_axi_arready(npu_s3_axi_arready ),
    .s05_axi_rid    (npu_s3_axi_rid     ),
    .s05_axi_rdata  (npu_s3_axi_rdata   ),
    .s05_axi_rresp  (npu_s3_axi_rresp   ),
    .s05_axi_rlast  (npu_s3_axi_rlast   ),
    .s05_axi_rvalid (npu_s3_axi_rvalid  ),
    .s05_axi_rready (npu_s3_axi_rready  ),
    .s05_axi_ruser  (),

    .s06_axi_awid(),
    .s06_axi_awaddr(),
    .s06_axi_awlen(),
    .s06_axi_awsize(),
    .s06_axi_awburst(),
    .s06_axi_awlock(),
    .s06_axi_awcache(),
    .s06_axi_awprot(),
    .s06_axi_awqos(),
    .s06_axi_awuser(),
    .s06_axi_awvalid(),
    .s06_axi_awready(),
    .s06_axi_wdata(),
    .s06_axi_wstrb(),
    .s06_axi_wlast(),
    .s06_axi_wuser(),
    .s06_axi_wvalid(),
    .s06_axi_wready(),
    .s06_axi_bid(),
    .s06_axi_bresp(),
    .s06_axi_buser(),
    .s06_axi_bvalid(),
    .s06_axi_bready(),
    .s06_axi_arid   (npu_s4_axi_arid    ),
    .s06_axi_araddr (npu_s4_axi_araddr  ),
    .s06_axi_arlen  (npu_s4_axi_arlen   ),
    .s06_axi_arsize (npu_s4_axi_arsize  ),
    .s06_axi_arburst(npu_s4_axi_arburst ),
    .s06_axi_arlock (npu_s4_axi_arlock  ),
    .s06_axi_arcache(npu_s4_axi_arcache ),
    .s06_axi_arprot (npu_s4_axi_arprot  ),
    .s06_axi_arqos  (4'd0),
    .s06_axi_aruser (),
    .s06_axi_arvalid(npu_s4_axi_arvalid ),
    .s06_axi_arready(npu_s4_axi_arready ),
    .s06_axi_rid    (npu_s4_axi_rid     ),
    .s06_axi_rdata  (npu_s4_axi_rdata   ),
    .s06_axi_rresp  (npu_s4_axi_rresp   ),
    .s06_axi_rlast  (npu_s4_axi_rlast   ),
    .s06_axi_rvalid (npu_s4_axi_rvalid  ),
    .s06_axi_rready (npu_s4_axi_rready  ),
    .s06_axi_ruser  (),

    /*
     * AXI master interface
     */
    // [WARB] M00 write parked: the arbiter drives the DDR write path now
    .m00_axi_awid    (arb2x_awid                     ),
    .m00_axi_awaddr  (arb2x_awaddr                   ),
    .m00_axi_awlen   (arb2x_awlen                    ),
    .m00_axi_awsize  (arb2x_awsize                   ),
    .m00_axi_awburst (arb2x_awburst                  ),
    .m00_axi_awlock  (arb2x_awlock                   ),
    .m00_axi_awcache (arb2x_awcache                  ),
    .m00_axi_awprot  (arb2x_awprot                   ),
    .m00_axi_awqos   (arb2x_awqos                    ),
    .m00_axi_awregion(),
    .m00_axi_awuser  (arb2x_awuser                   ),
    .m00_axi_awvalid (arb2x_awvalid                  ),
    .m00_axi_awready (1'b0                           ),  // never granted (write retired)
    .m00_axi_wdata   (arb2x_wdata                    ),
    .m00_axi_wstrb   (arb2x_wstrb                    ),
    .m00_axi_wlast   (arb2x_wlast                    ),
    .m00_axi_wuser   (arb2x_wuser                    ),
    .m00_axi_wvalid  (arb2x_wvalid                   ),
    .m00_axi_wready  (1'b0                           ),
    .m00_axi_bid     (                               ),
    .m00_axi_bresp   (                               ),
    .m00_axi_buser   (                               ),
    .m00_axi_bvalid  (                               ),
    .m00_axi_bready  (                               ),  // [WARB] crossbar out, unused: write retired
    .m00_axi_arid    (ddr_axi_aruser_id              ),
    .m00_axi_araddr  (ddr_axi_araddr                 ),
    .m00_axi_arlen   (ddr_axi_arlen                  ),
    .m00_axi_arsize  (ddr_axi_arsize                 ),
    .m00_axi_arburst (ddr_axi_arburst                ),
    .m00_axi_arlock  (ddr_axi_arlock                 ),
    .m00_axi_arcache (ddr_axi_arcache                ),
    .m00_axi_arprot  (ddr_axi_arprot                 ),
    .m00_axi_arqos   (ddr_axi_arqos                  ),
    .m00_axi_arregion(),
    .m00_axi_aruser  (ddr_axi_aruser                 ),
    .m00_axi_arvalid (ddr_axi_arvalid                ),
    .m00_axi_arready (ddr_axi_arready_xbar           ),  // [ARFIX] ack at latch
    .m00_axi_rid     (ddr_axi_rid                    ),
    .m00_axi_rdata   (ddr_axi_rdata                  ),
    .m00_axi_rresp   (2'b00                          ),
    .m00_axi_rlast   (ddr_axi_rlast                  ),
    .m00_axi_ruser   (ddr_axi_ruser                  ),
    .m00_axi_rvalid  (!ddr_axi_fifo_empty            ),
    .m00_axi_rready  (ddr_axi_rready                 ),





    .m01_axi_awid    (ovreg_axi_awid     ),
    .m01_axi_awaddr  (ovreg_axi_awaddr   ),
    .m01_axi_awlen   (ovreg_axi_awlen    ),
    .m01_axi_awsize  (ovreg_axi_awsize   ),
    .m01_axi_awburst (ovreg_axi_awburst  ),
    .m01_axi_awlock  (ovreg_axi_awlock   ),
    .m01_axi_awcache (ovreg_axi_awcache  ),
    .m01_axi_awprot  (ovreg_axi_awprot   ),
    .m01_axi_awqos   (ovreg_axi_awqos    ),
    .m01_axi_awregion(ovreg_axi_awregion),
    .m01_axi_awuser  (               ),
    .m01_axi_awvalid (ovreg_axi_awvalid  ),
    .m01_axi_awready (ovreg_axi_awready  ),
    .m01_axi_wdata   (ovreg_axi_wdata    ),
    .m01_axi_wstrb   (ovreg_axi_wstrb    ),
    .m01_axi_wlast   (ovreg_axi_wlast    ),
    .m01_axi_wuser   (               ),
    .m01_axi_wvalid  (ovreg_axi_wvalid   ),
    .m01_axi_wready  (ovreg_axi_wready   ),
    .m01_axi_bid     (ovreg_axi_bid      ),
    .m01_axi_bresp   (ovreg_axi_bresp    ),
    .m01_axi_buser   (               ),
    .m01_axi_bvalid  (ovreg_axi_bvalid   ),
    .m01_axi_bready  (ovreg_axi_bready   ),
    .m01_axi_arid    (ovreg_axi_arid     ),
    .m01_axi_araddr  (ovreg_axi_araddr   ),
    .m01_axi_arlen   (ovreg_axi_arlen    ),
    .m01_axi_arsize  (ovreg_axi_arsize   ),
    .m01_axi_arburst (ovreg_axi_arburst  ),
    .m01_axi_arlock  (ovreg_axi_arlock   ),
    .m01_axi_arcache (ovreg_axi_arcache  ),
    .m01_axi_arprot  (ovreg_axi_arprot   ),
    .m01_axi_arqos   (ovreg_axi_arqos    ),
    .m01_axi_arregion(ovreg_axi_arregion ),
    .m01_axi_aruser  (               ),
    .m01_axi_arvalid (ovreg_axi_arvalid  ),
    .m01_axi_arready (ovreg_axi_arready  ),
    .m01_axi_rid     (ovreg_axi_rid      ),
    .m01_axi_rdata   (ovreg_axi_rdata    ),
    .m01_axi_rresp   (ovreg_axi_rresp    ),
    .m01_axi_rlast   (ovreg_axi_rlast    ),
    .m01_axi_ruser   (              ),
    .m01_axi_rvalid  (ovreg_axi_rvalid   ),
    .m01_axi_rready  (ovreg_axi_rready   ),



    .m02_axi_awid    (npu_reg_axi_awid    ),
    .m02_axi_awaddr  (npu_reg_axi_awaddr  ),
    .m02_axi_awlen   (npu_reg_axi_awlen   ),
    .m02_axi_awsize  (npu_reg_axi_awsize  ),
    .m02_axi_awburst (npu_reg_axi_awburst ),
    .m02_axi_awlock  (npu_reg_axi_awlock  ),
    .m02_axi_awcache (npu_reg_axi_awcache ),
    .m02_axi_awprot  (npu_reg_axi_awprot  ),
    .m02_axi_awqos   (npu_reg_axi_awqos   ),
    .m02_axi_awregion(npu_reg_axi_awregion),
    .m02_axi_awvalid (npu_reg_axi_awvalid ),
    .m02_axi_awready (npu_reg_axi_awready ),
    .m02_axi_awuser  (  ),
    .m02_axi_wdata   (npu_reg_axi_wdata   ),
    .m02_axi_wstrb   (npu_reg_axi_wstrb   ),
    .m02_axi_wlast   (npu_reg_axi_wlast   ),
    .m02_axi_wvalid  (npu_reg_axi_wvalid  ),
    .m02_axi_wready  (npu_reg_axi_wready  ),
    .m02_axi_wuser   (  ),
    .m02_axi_bid     (npu_reg_axi_bid     ),
    .m02_axi_bresp   (npu_reg_axi_bresp   ),
    .m02_axi_bvalid  (npu_reg_axi_bvalid  ),
    .m02_axi_bready  (npu_reg_axi_bready  ),
    .m02_axi_buser   (  ),
    .m02_axi_arid    (npu_reg_axi_arid    ),
    .m02_axi_araddr  (npu_reg_axi_araddr  ),
    .m02_axi_arlen   (npu_reg_axi_arlen   ),
    .m02_axi_arsize  (npu_reg_axi_arsize  ),
    .m02_axi_arburst (npu_reg_axi_arburst ),
    .m02_axi_arlock  (npu_reg_axi_arlock  ),
    .m02_axi_arcache (npu_reg_axi_arcache ),
    .m02_axi_arprot  (npu_reg_axi_arprot  ),
    .m02_axi_arqos   (npu_reg_axi_arqos   ),
    .m02_axi_arregion(npu_reg_axi_arregion),
    .m02_axi_arvalid (npu_reg_axi_arvalid ),
    .m02_axi_arready (npu_reg_axi_arready ),
    .m02_axi_aruser  (  ),
    .m02_axi_rid     (npu_reg_axi_rid     ),
    .m02_axi_rdata   (npu_reg_axi_rdata   ),
    .m02_axi_rresp   (npu_reg_axi_rresp   ),
    .m02_axi_rlast   (npu_reg_axi_rlast   ),
    .m02_axi_ruser   (  ),
    .m02_axi_rvalid  (npu_reg_axi_rvalid  ),
    .m02_axi_rready  (npu_reg_axi_rready  )  




);

endmodule
