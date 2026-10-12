module fpga_v8_pcie_fifo_h2f_tc02 #(
    parameter ADDR_WIDTH = 12,
              MSI_NUM = 5,

    parameter   AXI_ID_LEN      = 4, 
		        AXI_DATA_LEN    = 128, 
		        AXI_DATA_SIZE   = $clog2(AXI_DATA_LEN/8), 	        
		        AXI_STRB_LEN    = AXI_DATA_LEN / 8               


)(
    input wire i_admit, input wire i_admit_axi,
    

    input                       button_rst_n    ,

    ////////////////// PCIE ////////////////
    input                       perst_n         ,
    input                       ref_clk_n       ,      
    input                       ref_clk_p       ,      
    input           [1:0]       rxn             ,
    input           [1:0]       rxp             ,
    output wire     [1:0]       txn             ,
    output wire     [1:0]       txp             ,
    output wire                 ref_led         ,
    output wire                 pclk_led        ,
    output wire                 smlh_link_up    ,
    output wire                 rdlh_link_up    ,

    output wire                 fifo_pcie_clk   ,
    output wire                 fifo_pcie_rst   , 

    input  [MSI_NUM-2 : 0]      i_msi_req       ,
    output [MSI_NUM-2 : 0]      o_msi_grant     ,

    ///////////////// AXI FOR DDR3 //////////////////////////////
    input                               axi_clk,
    input                               axi_rst,

    output       [AXI_ID_LEN-1:0]       axi_awid        /* synthesis PAP_MARK_DEBUG="true" */,
    output       [31:0]                 axi_awaddr      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 3:0]                 axi_awlen       /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 2:0]                 axi_awsize      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 1:0]                 axi_awburst     /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_awlock      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 3:0]                 axi_awcache     /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 2:0]                 axi_awprot      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 3:0]                 axi_awqos       /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_awvalid     /* synthesis PAP_MARK_DEBUG="true" */,
    input                               axi_awready     /* synthesis PAP_MARK_DEBUG="true" */,
    
    output       [AXI_DATA_LEN-1:0]     axi_wdata       /* synthesis PAP_MARK_DEBUG="true" */,
    output       [AXI_STRB_LEN-1:0]     axi_wstrb       /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_wlast       /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_wvalid      /* synthesis PAP_MARK_DEBUG="true" */,
    input                               axi_wready      /* synthesis PAP_MARK_DEBUG="true" */,
    
    input        [AXI_ID_LEN-1:0]       axi_bid         /* synthesis PAP_MARK_DEBUG="true" */,
    input        [ 1:0]                 axi_bresp       /* synthesis PAP_MARK_DEBUG="true" */,
    input                               axi_bvalid      /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_bready      /* synthesis PAP_MARK_DEBUG="true" */,
    
    output       [AXI_ID_LEN-1:0]       axi_arid        /* synthesis PAP_MARK_DEBUG="true" */,
    output       [31:0]                 axi_araddr      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 3:0]                 axi_arlen       /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 2:0]                 axi_arsize      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 1:0]                 axi_arburst     /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_arlock      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 3:0]                 axi_arcache     /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 2:0]                 axi_arprot      /* synthesis PAP_MARK_DEBUG="true" */,
    output       [ 3:0]                 axi_arqos       /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_arvalid     /* synthesis PAP_MARK_DEBUG="true" */,
    input                               axi_arready     /* synthesis PAP_MARK_DEBUG="true" */,
    
    input        [AXI_ID_LEN-1:0]       axi_rid         /* synthesis PAP_MARK_DEBUG="true" */,
    input        [AXI_DATA_LEN-1:0]     axi_rdata       /* synthesis PAP_MARK_DEBUG="true" */,
    input        [ 1:0]                 axi_rresp       /* synthesis PAP_MARK_DEBUG="true" */,
    input                               axi_rlast       /* synthesis PAP_MARK_DEBUG="true" */,
    input                               axi_rvalid      /* synthesis PAP_MARK_DEBUG="true" */,
    output                              axi_rready      /* synthesis PAP_MARK_DEBUG="true" */,
    output wire startup_idle_axi, startup_idle_pcie
);
wire rx_retirement_epoch_rst;
reg rx_retired_toggle;
reg rx_retired_seen;
wire    [31:0]              fpga_ddr3_addr   ;
wire    [31:0]              fpga_ddr3_length ;
wire    [31:0]              fpga_ddr3_total_length ;
wire                        mrd_rx_busy;
wire                        fpga_rx_clk_en   ;
wire     [ADDR_WIDTH-1:0]   fpga_rx_addr     ;
wire     [127:0]            fpga_rx_data     ;
reg                         mrd_rx_busy_r    ;
wire                        mrd_rx_falling   ;
reg                         fpga_rx_clk_en_r ;
reg     [ADDR_WIDTH-1:0]    fpga_rx_addr_r   ;
localparam S_DATA_WRY_IDLE   = 1'd0;
localparam S_DATA_WRY_CHECK  = 1'd1;
reg  data_wry_state;
reg  data_wry_state_next;
reg fpga_data_valid_pulse;
wire fpga_data_valid;
wire [31:0] total_beats    /* synthesis PAP_MARK_DEBUG="true" */;
wire [31:0] dma_total_beats/* synthesis PAP_MARK_DEBUG="true" */;
reg [31:0] rx_cnt;
reg [31:0] rx_bytes_total, rx_chunk_bytes;
reg [127:0] rx_pack_data, rx_fifo_write_data;
reg [4:0] rx_pack_bytes;
reg rx_fifo_write_en, rx_copy_active, rx_transaction_complete;
reg fpga_rx_clk_en_d;
reg fpga_rx_done;
reg [4:0] rx_input_bytes;
wire [127:0] rx_input_mask;
wire [255:0] rx_merge_data;
wire [5:0] rx_merge_bytes;
wire                        mwr_tx_busy                ;
wire                        fpga_data_ready            ;
wire                        fpga_tx_done               ;
wire                        fpga_tx_clk_en             ;
wire     [ADDR_WIDTH-1:0]   fpga_tx_addr               /* synthesis PAP_MARK_DEBUG="true" */;
wire     [127:0]            fpga_tx_data               ;
wire [127:0] fifo_rx_data /* synthesis PAP_MARK_DEBUG="true" */;
wire         fifo_rx_empty/* synthesis PAP_MARK_DEBUG="true" */;
wire         fifo_rx_rd_en/* synthesis PAP_MARK_DEBUG="true" */;
wire [9 : 0] fifo_rx_water_level;
wire [31:0] last_beat_bytes/* synthesis PAP_MARK_DEBUG="true" */;
wire [15:0] last_beat_strb /* synthesis PAP_MARK_DEBUG="true" */;
localparam S_IDLE=3'd0, S_ADDR_SEND=3'd1, S_WDATA_SEND=3'd2;
localparam S_BRESP_WAIT=3'd3, S_WRITW_DATA=3'd4;
reg [2:0] state;
reg [31:0] cur_addr, beats_remain;
reg [15:0] cur_strb;
reg [4:0] burst_beats, reads_issued, wbeat_cnt;
reg [1:0] rx_w_queue_count;
reg [127:0] rx_w_q0, rx_w_q1;
reg rx_read_pending, axi_b_resp_error;
wire rx_w_fire;
wire rx_b_fire;
wire [2:0] rx_reserved_after_pop;
wire         fifo_tx_empty/* synthesis PAP_MARK_DEBUG="true" */;
wire [9 : 0] fifo_tx_water_level/* synthesis PAP_MARK_DEBUG="true" */;
wire         fifo_tx_almost_full/* synthesis PAP_MARK_DEBUG="true" */;
wire full/* synthesis PAP_MARK_DEBUG="true" */;
wire  mwr_tx_busy_rising /* synthesis PAP_MARK_DEBUG="true" */;
reg  mwr_tx_busy_d;
localparam S_DATA_RDY_IDLE   = 1'd0;
localparam S_DATA_RDY_CHECK  = 1'd1;
reg  data_rdy_state;
reg  data_rdy_state_next;
reg fpga_data_ready_r;
reg  [31:0] tx_cnt/* synthesis PAP_MARK_DEBUG="true" */;
reg  [31:0] tx_beat_cnt/* synthesis PAP_MARK_DEBUG="true" */;
reg        fpga_tx_done_r;
reg tx_runing;
reg tx_runing_axi;
reg tx_runing_axi_d1;
reg tx_runing_axi_d2;
wire tx_runing_axi_rising;
reg [31:0] r_cur_addr;
reg [31:0] read_beats_remain /* synthesis PAP_MARK_DEBUG="true" */;
reg        read_started /* synthesis PAP_MARK_DEBUG="true" */;
localparam R_IDLE       = 2'd0;
localparam R_ADDR_SEND  = 2'd1;
localparam R_DATA_WAIT  = 2'd2;
localparam R_DONE       = 2'd3;
reg [1:0] r_state/* synthesis PAP_MARK_DEBUG="true" */;
reg [1:0] r_next;
wire [3:0] r_burst_len;
reg  fifo_tx_wr_en;
reg  [127:0] fifo_tx_wr_data;
wire fifo_rx_almost_full;

assign startup_idle_axi = (state == S_IDLE) && !rx_read_pending &&
    (rx_w_queue_count == 0) && (r_state == R_IDLE) && !read_started;
assign startup_idle_pcie = !mrd_rx_busy && !mwr_tx_busy && !rx_copy_active &&
    !fpga_rx_clk_en_r && !fpga_rx_clk_en_d && !rx_fifo_write_en &&
    (data_wry_state == S_DATA_WRY_IDLE);

// Included as text by the isolated candidate generator, after the FIFO ports.
// This handshake requires COORDINATED PCIe + AXI fabric/endpoint reset.
// Independent link/CPU reset is not a supported pending-DMA cleanup path.
assign rx_retirement_epoch_rst = axi_rst | fifo_pcie_rst;
// Assert both new handshake domains asynchronously, release in each clock.
(* ASYNC_REG = "TRUE" *) reg rx_retire_axi_rst1, rx_retire_axi_rst2;
(* ASYNC_REG = "TRUE" *) reg rx_retire_pcie_rst1, rx_retire_pcie_rst2;
always @(posedge axi_clk or posedge rx_retirement_epoch_rst) begin
    if (rx_retirement_epoch_rst) begin
        rx_retire_axi_rst1 <= 1'b1;
        rx_retire_axi_rst2 <= 1'b1;
    end else begin
        rx_retire_axi_rst1 <= 1'b0;
        rx_retire_axi_rst2 <= rx_retire_axi_rst1;
    end
end
always @(posedge fifo_pcie_clk or posedge rx_retirement_epoch_rst) begin
    if (rx_retirement_epoch_rst) begin
        rx_retire_pcie_rst1 <= 1'b1;
        rx_retire_pcie_rst2 <= 1'b1;
    end else begin
        rx_retire_pcie_rst1 <= 1'b0;
        rx_retire_pcie_rst2 <= rx_retire_pcie_rst1;
    end
end

(* ASYNC_REG = "TRUE" *) reg rx_retired_sync1, rx_retired_sync2;


// One persistent credit for each complete H2F transaction. Intermediate
// chunks and intermediate bursts cannot produce a credit. BRESP errors still
// retire: the host sees DeliveryKnownUnknownResponse and must read back state.
always @(posedge axi_clk or posedge rx_retire_axi_rst2) begin
    if (rx_retire_axi_rst2)
        rx_retired_toggle <= 1'b0;
    else if ((state == S_BRESP_WAIT) && (beats_remain == 32'd0) &&
             axi_bvalid && axi_bready && (axi_bid == {AXI_ID_LEN{1'b0}}))
        rx_retired_toggle <= ~rx_retired_toggle;
end

always @(posedge fifo_pcie_clk or posedge rx_retire_pcie_rst2) begin
    if (rx_retire_pcie_rst2) begin
        rx_retired_sync1 <= 1'b0;
        rx_retired_sync2 <= 1'b0;
    end else begin
        rx_retired_sync1 <= rx_retired_toggle;
        rx_retired_sync2 <= rx_retired_sync1;
    end
end

// Consume only at final total completion; never consume at an intermediate
// chunk. The completed toggle remains different from seen until consumed.
// Previously consumed retirement cannot authorize a later command.
always @(posedge fifo_pcie_clk or posedge rx_retire_pcie_rst2) begin
    if (rx_retire_pcie_rst2)
        rx_retired_seen <= 1'b0;
    else if (!fpga_data_valid && !fpga_rx_done && rx_transaction_complete &&
             (rx_cnt == dma_total_beats) && fifo_rx_empty &&
             (rx_retired_sync2 != rx_retired_seen))
        rx_retired_seen <= rx_retired_sync2;
end



//----------------------------------------
// CPU --> FPGA RX FIFO
//----------------------------------------

              //rx
              //rx
        //tx







// reg                         mrd_rx_rase      ;




// mrd_rx_busy falling edge detection
always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        mrd_rx_busy_r <= 1'b0;
    end 
    else begin
        mrd_rx_busy_r <= mrd_rx_busy;
        // mrd_rx_rase   <= ~mrd_rx_busy_r & mrd_rx_busy;
    end
end
assign mrd_rx_falling = mrd_rx_busy_r & ~mrd_rx_busy;

////////////////////////////////////////




always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        data_wry_state <= S_DATA_WRY_IDLE;
    end else begin
        data_wry_state <= data_wry_state_next;
    end
end

always @(*) begin
    case (data_wry_state)
        S_DATA_WRY_IDLE:  data_wry_state_next = mrd_rx_falling  ? S_DATA_WRY_CHECK : S_DATA_WRY_IDLE;
        S_DATA_WRY_CHECK: data_wry_state_next = fifo_rx_almost_full ? S_DATA_WRY_CHECK : S_DATA_WRY_IDLE;
        default:          data_wry_state_next = S_DATA_WRY_IDLE;
    endcase
end


always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        fpga_data_valid_pulse <= 1'b0;
    end 
    else begin
        fpga_data_valid_pulse <= ((data_wry_state == S_DATA_WRY_CHECK) && !fifo_rx_almost_full) ;
    end
end

assign fpga_data_valid = fpga_data_valid_pulse;

///////////////////////////////////////////////

assign total_beats     = (fpga_ddr3_length[31:4] + |fpga_ddr3_length[3:0]);  // ceil(len/16)

assign dma_total_beats = (fpga_ddr3_total_length[31:4] + |fpga_ddr3_total_length[3:0]);  // ceil(len/16)
// H2F chunk RAM reads have one clock latency. Keep partial 128-bit words
// across chunks, so a 4092-byte intermediate chunk contributes 255 full words
// and 12 carry bytes, never a padded word in the middle of a transfer.








always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) rx_input_bytes <= 0;
    else if (fpga_rx_clk_en_r)
        rx_input_bytes <= (fpga_rx_addr_r == total_beats-1 &&
                           fpga_ddr3_length[3:0] != 0) ?
                           {1'b0,fpga_ddr3_length[3:0]} : 5'd16;
end
assign rx_input_mask = {128{1'b1}} >> ((32'd16-rx_input_bytes)*8);
assign rx_merge_data = {128'd0,rx_pack_data} |
    ({128'd0,(fpga_rx_data & rx_input_mask)} << (rx_pack_bytes*8));
assign rx_merge_bytes = {1'b0,rx_pack_bytes}+{1'b0,rx_input_bytes};
assign fpga_rx_clk_en = fpga_rx_clk_en_r;
assign fpga_rx_addr = fpga_rx_addr_r;

always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        fpga_rx_clk_en_r <= 0; fpga_rx_clk_en_d <= 0;
        fpga_rx_addr_r <= 0; rx_cnt <= 0;
        rx_bytes_total <= 0; rx_chunk_bytes <= 0;
        rx_pack_data <= 0; rx_pack_bytes <= 0;
        rx_fifo_write_en <= 0; rx_fifo_write_data <= 0;
        rx_copy_active <= 0; rx_transaction_complete <= 0;
        fpga_rx_done <= 0;
    end else begin
        fpga_rx_clk_en_d <= fpga_rx_clk_en_r;
        rx_fifo_write_en <= 0;
        if (rx_fifo_write_en) rx_cnt <= rx_cnt + 1'b1;
        if (fpga_data_valid) begin
            fpga_rx_clk_en_r <= 1;
            fpga_rx_addr_r <= 0;
            rx_chunk_bytes <= 0;
            rx_copy_active <= 1;
            fpga_rx_done <= 0;
            if (rx_transaction_complete) begin
                rx_cnt <= 0; rx_bytes_total <= 0;
                rx_pack_data <= 0; rx_pack_bytes <= 0;
            end
            rx_transaction_complete <= 0;
        end else begin
            if (fpga_rx_clk_en_r) begin
                if (fpga_rx_addr_r == total_beats-1)
                    fpga_rx_clk_en_r <= 0;
                fpga_rx_addr_r <= fpga_rx_addr_r + 1'b1;
            end
            if (fpga_rx_clk_en_d) begin
                rx_chunk_bytes <= rx_chunk_bytes + rx_input_bytes;
                rx_bytes_total <= rx_bytes_total + rx_input_bytes;
                if (rx_merge_bytes >= 16) begin
                    rx_fifo_write_en <= 1;
                    rx_fifo_write_data <= rx_merge_data[127:0];
                    rx_pack_data <= rx_merge_data[255:128];
                    rx_pack_bytes <= rx_merge_bytes-16;
                end else begin
                    rx_pack_data <= rx_merge_data[127:0];
                    rx_pack_bytes <= rx_merge_bytes;
                end
            end else if (rx_copy_active && !fpga_rx_clk_en_r && !rx_fifo_write_en) begin
                if ((rx_bytes_total == fpga_ddr3_total_length) && (rx_pack_bytes != 0)) begin
                    // Only the final transaction word is zero padded.
                    rx_fifo_write_en <= 1;
                    rx_fifo_write_data <= rx_pack_data;
                    rx_pack_data <= 0; rx_pack_bytes <= 0;
                end else begin
                    rx_copy_active <= 0;
                    if (rx_bytes_total == fpga_ddr3_total_length)
                        rx_transaction_complete <= 1;
                    else
                        fpga_rx_done <= 1;
                end
            end
            if (i_admit && rx_transaction_complete && (rx_cnt == dma_total_beats) &&
                fifo_rx_empty && (rx_retired_sync2 != rx_retired_seen))
                fpga_rx_done <= 1;
        end
    end
end


//////////////tx/////////////////








fpga_v8_pango_pcie_top_h2f_rfg01 #(
    .ADDR_WIDTH(ADDR_WIDTH),
    .MSI_NUM(MSI_NUM)
)
pango_pcie_top(
    .i_admit(i_admit),
    .button_rst_n(button_rst_n)    ,
    .perst_n     (perst_n     )    ,
    .ref_clk_n   (ref_clk_n)      ,
    .ref_clk_p   (ref_clk_p)      ,
    .rxn         (rxn)        ,
    .rxp         (rxp)        ,
    .txn         (txn)        ,
    .txp         (txp)        ,
    .ref_led     (ref_led     )    ,
    .pclk_led    (pclk_led    )    ,
    .smlh_link_up(smlh_link_up)    ,
    .rdlh_link_up(rdlh_link_up)    ,

    .i_msi_req  (i_msi_req    )    ,
    .o_msi_grant(o_msi_grant  )    ,

    .fpga_ddr3_addr   (fpga_ddr3_addr   ),
    .fpga_ddr3_length (fpga_ddr3_length ),
    .fpga_ddr3_total_length(fpga_ddr3_total_length),
    //FPGA --> CPU
    .fpga_tx_done     (fpga_tx_done     ),     
    .mwr_tx_busy      (mwr_tx_busy      ),
    .fpga_data_ready  (fpga_data_ready  ),     
    .fpga_tx_clk_en   (fpga_tx_clk_en   ),
    .fpga_tx_addr     (fpga_tx_addr     ),      //没用
    .fpga_tx_data     (fpga_tx_data     ),
    //CPU --> FPGA
    .fpga_rx_done     (fpga_rx_done && i_admit),     
    .mrd_rx_busy      (mrd_rx_busy      ),
    .fpga_rx_clk_en   (fpga_rx_clk_en   ),
    .fpga_rx_addr     (fpga_rx_addr     ),
    .fpga_rx_data     (fpga_rx_data     ),

    .fifo_pcie_clk    (fifo_pcie_clk)    ,
    .fifo_pcie_rst    (fifo_pcie_rst)
);









pcie_rx_fifo pcie_rx_fifo (
  .wr_clk       (fifo_pcie_clk      ),
  .wr_rst       (fifo_pcie_rst      ),
  .wr_en        (rx_fifo_write_en   ),
  .wr_data      (rx_fifo_write_data ),
  .wr_full      (                   ),
  .almost_full  (fifo_rx_almost_full),
  .rd_clk       (axi_clk            ),
  .rd_rst       (axi_rst            ),
  .rd_en        (fifo_rx_rd_en      ),
  .rd_data      (fifo_rx_data       ),
  .rd_empty     (fifo_rx_empty      ),
  .rd_water_level(fifo_rx_water_level),    // output [9:0]
  .almost_empty (                   )
);



// 突发参数计算




assign last_beat_bytes = |fpga_ddr3_total_length[3:0] ? fpga_ddr3_total_length[3:0] : 32'd16;

// 最后 beat 的字节掩码
assign last_beat_strb  = (last_beat_bytes == 32'd1)  ? 16'b0000_0000_0000_0001 :
                         (last_beat_bytes == 32'd2)  ? 16'b0000_0000_0000_0011 :
                         (last_beat_bytes == 32'd3)  ? 16'b0000_0000_0000_0111 :
                         (last_beat_bytes == 32'd4)  ? 16'b0000_0000_0000_1111 :
                         (last_beat_bytes == 32'd5)  ? 16'b0000_0000_0001_1111 :
                         (last_beat_bytes == 32'd6)  ? 16'b0000_0000_0011_1111 :
                         (last_beat_bytes == 32'd7)  ? 16'b0000_0000_0111_1111 :
                         (last_beat_bytes == 32'd8)  ? 16'b0000_0000_1111_1111 :
                         (last_beat_bytes == 32'd9)  ? 16'b0000_0001_1111_1111 :
                         (last_beat_bytes == 32'd10) ? 16'b0000_0011_1111_1111 :
                         (last_beat_bytes == 32'd11) ? 16'b0000_0111_1111_1111 :
                         (last_beat_bytes == 32'd12) ? 16'b0000_1111_1111_1111 :
                         (last_beat_bytes == 32'd13) ? 16'b0001_1111_1111_1111 :
                         (last_beat_bytes == 32'd14) ? 16'b0011_1111_1111_1111 :
                         (last_beat_bytes == 32'd15) ? 16'b0111_1111_1111_1111 :
                                                       16'b1111_1111_1111_1111 ;




//====================================================
// AXI Write Interface Logic (With B channel)
//====================================================

// One outstanding AXI burst. Every FIFO read reserves a response slot before
// the synchronous RAM is clocked. The pending bit is the one-clock read
// latency; the two-word queue holds returned data across arbitrary W stalls.









assign rx_w_fire = axi_wvalid && axi_wready;
assign rx_b_fire = axi_bvalid && axi_bready && (axi_bid == {AXI_ID_LEN{1'b0}});
assign rx_reserved_after_pop = {1'b0,rx_w_queue_count} +
                                {2'b0,rx_read_pending} - {2'b0,rx_w_fire};
assign fifo_rx_rd_en = (state == S_WDATA_SEND) && !fifo_rx_empty &&
                      (reads_issued < burst_beats) && (rx_reserved_after_pop < 2);
assign axi_awid = {AXI_ID_LEN{1'b0}};
assign axi_awaddr = cur_addr;
assign axi_awlen = burst_beats - 1'b1;
assign axi_awsize = AXI_DATA_SIZE;
assign axi_awburst = 2'b01;
assign axi_awlock = 0;
assign axi_awcache = 4'b0010;
assign axi_awprot = 0;
assign axi_awqos = 0;
assign axi_awvalid = (state == S_ADDR_SEND);
assign axi_wdata = rx_w_q0;
assign axi_wvalid = (state == S_WDATA_SEND) && (rx_w_queue_count != 0);
assign axi_wlast = (wbeat_cnt == burst_beats-1'b1);
assign axi_wstrb = (axi_wlast && (beats_remain <= {27'd0,burst_beats})) ? cur_strb : 16'hffff;
assign axi_bready = (state == S_BRESP_WAIT);

always @(posedge axi_clk) begin
    if (axi_rst) begin
        state <= S_IDLE; cur_addr <= 0; cur_strb <= 16'hffff;
        beats_remain <= 0; burst_beats <= 1;
        reads_issued <= 0; wbeat_cnt <= 0;
        rx_read_pending <= 0; rx_w_queue_count <= 0;
        rx_w_q0 <= 0; rx_w_q1 <= 0; axi_b_resp_error <= 0;
    end else begin
        rx_read_pending <= fifo_rx_rd_en;
        if (fifo_rx_rd_en) reads_issued <= reads_issued + 1'b1;
        case ({rx_read_pending,rx_w_fire})
            2'b10: begin
                if (rx_w_queue_count == 0) rx_w_q0 <= fifo_rx_data;
                else rx_w_q1 <= fifo_rx_data;
                rx_w_queue_count <= rx_w_queue_count + 1'b1;
            end
            2'b01: begin
                if (rx_w_queue_count == 2) rx_w_q0 <= rx_w_q1;
                rx_w_queue_count <= rx_w_queue_count - 1'b1;
            end
            2'b11: begin
                if (rx_w_queue_count == 1) rx_w_q0 <= fifo_rx_data;
                else begin rx_w_q0 <= rx_w_q1; rx_w_q1 <= fifo_rx_data; end
            end
        endcase
        case (state)
            S_IDLE: if (i_admit_axi && !fifo_rx_empty) begin
                cur_addr <= {(fpga_ddr3_addr >> AXI_DATA_SIZE),{AXI_DATA_SIZE{1'b0}}};
                cur_strb <= last_beat_strb;
                beats_remain <= dma_total_beats;
                burst_beats <= (dma_total_beats >= 16) ? 5'd16 : dma_total_beats[4:0];
                reads_issued <= 0; wbeat_cnt <= 0; axi_b_resp_error <= 0;
                state <= S_ADDR_SEND;
            end
            S_ADDR_SEND: if (axi_awvalid && axi_awready) state <= S_WDATA_SEND;
            S_WDATA_SEND: if (rx_w_fire) begin
                wbeat_cnt <= wbeat_cnt + 1'b1;
                if (axi_wlast) begin
                    // Widen before arithmetic: a 16-beat burst is 256 bytes.
                    cur_addr <= cur_addr + ({27'd0,burst_beats} << 4);
                    beats_remain <= beats_remain - {27'd0,burst_beats};
                    state <= S_BRESP_WAIT;
                end
            end
            S_BRESP_WAIT: if (rx_b_fire) begin
                axi_b_resp_error <= (axi_bresp != 0);
                state <= (beats_remain == 0) ? S_IDLE : S_WRITW_DATA;
            end
            S_WRITW_DATA: if (!axi_b_resp_error) begin
                burst_beats <= (beats_remain >= 16) ? 5'd16 : beats_remain[4:0];
                reads_issued <= 0; wbeat_cnt <= 0;
                state <= S_ADDR_SEND;
            end
        endcase
    end
end


////////////////////////////////////////////////////////////////////////




pcie_tx_fifo pcie_tx_fifo (
  .wr_clk       (axi_clk            ),
  .wr_rst       (axi_rst            ),
  .wr_en        (fifo_tx_wr_en      ),
  .wr_data      (fifo_tx_wr_data    ),
  .wr_full      (full                ),
  .almost_full  (fifo_tx_almost_full ),
  .rd_clk       (fifo_pcie_clk       ),
  .rd_rst       (fifo_pcie_rst       ),
  .rd_en        (fpga_tx_clk_en      ),
  .rd_data      (fpga_tx_data        ),
  .rd_empty     (fifo_tx_empty       ),
  .rd_water_level(fifo_tx_water_level),
  .almost_empty (                    )
);





////////////////////////////////////////////////////////////////////////
// FPGA --> CPU TX Data Ready Logic
////////////////////////////////////////////////////////////////////////


always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        mwr_tx_busy_d <= 1'b0;
    end else begin
        mwr_tx_busy_d <= mwr_tx_busy;
    end
end
assign mwr_tx_busy_rising = ~mwr_tx_busy_d & mwr_tx_busy;





always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        data_rdy_state <= S_DATA_RDY_IDLE;
    end else begin
        data_rdy_state <= data_rdy_state_next;
    end
end

always @(*) begin
    case (data_rdy_state)
        S_DATA_RDY_IDLE:  data_rdy_state_next = mwr_tx_busy_rising  ? S_DATA_RDY_CHECK : S_DATA_RDY_IDLE;
        S_DATA_RDY_CHECK: data_rdy_state_next = (!fifo_tx_empty && (fifo_tx_water_level >= total_beats[9:0]))
                                               ? S_DATA_RDY_IDLE : S_DATA_RDY_CHECK;
        default:          data_rdy_state_next = S_DATA_RDY_IDLE;
    endcase
end


always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        fpga_data_ready_r <= 1'b0;
    end
    else if(mwr_tx_busy_rising) begin
        fpga_data_ready_r <= 1'b0;
    end
    else if(data_rdy_state == S_DATA_RDY_CHECK) begin
        fpga_data_ready_r <= (!fifo_tx_empty && (fifo_tx_water_level >= total_beats[9:0])) ;
    end
end

assign fpga_data_ready = fpga_data_ready_r;

////////////////////////////////////////////////////////////////////////
// FPGA --> CPU TX Done Logic
////////////////////////////////////////////////////////////////////////
  //总操作beat数



always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        tx_beat_cnt    <= 32'd0;
    end 
    else if(tx_beat_cnt == total_beats) begin
        tx_beat_cnt <= 32'd0;
    end
    else if (fpga_tx_clk_en) begin
        tx_beat_cnt  <= tx_beat_cnt + 1'd1; 
    end
end

always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        fpga_tx_done_r <= 1'b0;
    end
    else if(tx_beat_cnt == total_beats) begin
        fpga_tx_done_r <= 1'b1;
    end
    else if(mwr_tx_busy_rising) begin
        fpga_tx_done_r <= 1'b0;
    end
end
assign fpga_tx_done = fpga_tx_done_r;



always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        tx_cnt <= 32'd0;
    end 
    else if (tx_cnt == dma_total_beats) begin
        tx_cnt <= 32'd0;
    end 
    else if (fpga_tx_clk_en) begin
        tx_cnt <= tx_cnt + 1'd1; 
    end
end

///////////////////////// AXI_read ////////////////////////////////

//====================================================
// AXI Read Interface Logic
//====================================================

always @(posedge fifo_pcie_clk or posedge fifo_pcie_rst) begin
    if (fifo_pcie_rst) begin
        tx_runing <= 1'b0;
    end
    else if(tx_cnt == dma_total_beats) begin
        tx_runing <= 1'b0;
    end
    else if(mwr_tx_busy_rising) begin
        tx_runing <= 1'b1;
    end
end


//----------- CDC: tx_runing from fifo_pcie_clk to axi_clk ----------



always @(posedge axi_clk or posedge axi_rst) begin
    if (axi_rst) begin
        tx_runing_axi   <= 1'b0;
        tx_runing_axi_d1 <= 1'b0;
        tx_runing_axi_d2 <= 1'b0;
    end else begin
        tx_runing_axi    <= tx_runing;
        tx_runing_axi_d1 <= tx_runing_axi;
        tx_runing_axi_d2 <= tx_runing_axi_d1;
    end
end

assign tx_runing_axi_rising = tx_runing_axi_d1 && ~tx_runing_axi_d2;

//----------- Read Start & Base Address Latch ----------




always @(posedge axi_clk or posedge axi_rst) begin
    if (axi_rst) begin
        read_beats_remain <= 32'd0;
        read_started      <= 1'b0;
    end
    else if (tx_runing_axi_rising) begin
        read_beats_remain <= dma_total_beats;
        read_started      <= 1'b1;
    end
    else if (axi_rvalid && axi_rready && axi_rlast && (axi_rid == 4'b0000)) begin
        read_beats_remain <= read_beats_remain - (axi_arlen + 4'd1);
    end
    else if (read_started && read_beats_remain == 32'd0) begin
        read_started <= 1'b0;
    end
end


/////////////////////////////////////////
// reg test /* synthesis PAP_MARK_DEBUG="true" */;
// always @(posedge axi_clk or posedge axi_rst) begin
//     if (axi_rst) begin
//         test <= 1'b0;
//     end
//     else if(axi_rvalid && axi_rready && (axi_araddr > 32'h1c2000 + 32'h003F8400)) begin
//         test <= 1'b1;
//     end
// end
//////////////////////////////////////////

// Current address update
always @(posedge axi_clk or posedge axi_rst) begin
    if (axi_rst) begin
        r_cur_addr <= 32'd0;
    end
    else if (tx_runing_axi_rising) begin
        r_cur_addr <= {(fpga_ddr3_addr >> AXI_DATA_SIZE), {AXI_DATA_SIZE{1'b0}}};
    end
    else if (axi_rvalid && axi_rready && axi_rlast && (axi_rid == 4'b0000)) begin
        r_cur_addr <= r_cur_addr + ((axi_arlen + 4'd1) << 4);  // Advance by beats * 16 bytes
    end
end

//----------- Read Address State Machine ----------









always @(posedge axi_clk or posedge axi_rst) begin
    if (axi_rst)
        r_state <= R_IDLE;
    else
        r_state <= r_next;
end

always @(*) begin
    case (r_state)
        R_IDLE:      r_next = (read_started && !fifo_tx_almost_full) ? R_ADDR_SEND : R_IDLE;
        R_ADDR_SEND: r_next = (axi_arvalid && axi_arready) ? R_DATA_WAIT : R_ADDR_SEND;
        R_DATA_WAIT: r_next = (axi_rvalid && axi_rready && axi_rlast && (axi_rid == 4'b0000)) ? R_DONE : R_DATA_WAIT;
        R_DONE:      r_next = (read_beats_remain == 32'd0) ? R_IDLE : (fifo_tx_almost_full ? R_DONE : R_ADDR_SEND);
        default:     r_next = R_IDLE;
    endcase
end


//----------- Burst Length Calculation ----------
assign r_burst_len = (read_beats_remain >= 32'd16) ? 4'd15 :
                          (read_beats_remain[3:0] == 4'd0) ? 4'd15 :
                          (read_beats_remain[3:0] - 4'd1);

//----------- AR Signal Assignments ----------
assign axi_arlen      = r_burst_len;
assign axi_araddr     = r_cur_addr;
assign axi_arsize     = AXI_DATA_SIZE;   // 4 (16 bytes per beat)
assign axi_arburst    = 2'b01;           // INCR burst
assign axi_arlock     = 1'b0;
assign axi_arcache    = 4'b0010;         // Normal non-cacheable
assign axi_arprot     = 3'b000;
assign axi_arqos      = 4'd0;
assign axi_aruser_ap  = 1'b0;
assign axi_aruser_id  = 4'd0;
assign axi_arid       = 4'd0;

// reg ar_sent;
// always @(posedge axi_clk or posedge axi_rst) begin
//     if (axi_rst)
//         ar_sent <= 1'b0;
//     else if (r_state == R_INIT)
//         ar_sent <= 1'b0;
//     else if (r_state == R_ADDR_SEND && axi_arvalid && axi_arready)
//         ar_sent <= 1'b1;
// end

assign axi_arvalid = (r_state == R_ADDR_SEND);// && !ar_sent;

//----------- RREADY & FIFO Write ----------
assign axi_rready = (r_state == R_DATA_WAIT);

//----------- FIFO Write Interface ----------




always @(posedge axi_clk or posedge axi_rst) begin
    if (axi_rst) begin
        fifo_tx_wr_en    <= 1'b0;
        fifo_tx_wr_data  <= 128'd0;
    end
    else begin
        fifo_tx_wr_en    <= axi_rvalid && axi_rready && (axi_rid == 4'b0000);
        fifo_tx_wr_data  <= axi_rdata;
    end
end

// //----------- Read Done Tracking ----------
// reg read_done_r;
// always @(posedge axi_clk or posedge axi_rst) begin
//     if (axi_rst)
//         read_done_r <= 1'b0;
//     else if (r_state == R_DATA_WAIT && axi_rvalid && axi_rready && axi_rlast && (read_beats_remain == 32'd0))
//         read_done_r <= 1'b1;
//     else
//         read_done_r <= 1'b0;
// end

//====================================================
// AXI Read Interface Logic - END
//====================================================

endmodule
