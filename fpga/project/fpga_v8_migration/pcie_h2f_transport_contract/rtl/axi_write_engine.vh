// One outstanding AXI burst. Every FIFO read reserves a response slot before
// the synchronous RAM is clocked. The pending bit is the one-clock read
// latency; the two-word queue holds returned data across arbitrary W stalls.
localparam S_IDLE=3'd0, S_ADDR_SEND=3'd1, S_WDATA_SEND=3'd2;
localparam S_BRESP_WAIT=3'd3, S_WRITW_DATA=3'd4;
reg [2:0] state;
reg [31:0] cur_addr, beats_remain;
reg [15:0] cur_strb;
reg [4:0] burst_beats, reads_issued, wbeat_cnt;
reg [1:0] rx_w_queue_count;
reg [127:0] rx_w_q0, rx_w_q1;
reg rx_read_pending, axi_b_resp_error;
wire rx_w_fire = axi_wvalid && axi_wready;
wire rx_b_fire = axi_bvalid && axi_bready && (axi_bid == {AXI_ID_LEN{1'b0}});
wire [2:0] rx_reserved_after_pop = {1'b0,rx_w_queue_count} +
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
            S_IDLE: if (!fifo_rx_empty) begin
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
