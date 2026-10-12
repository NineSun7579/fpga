// Isolated actual V5 ov5640_ddr candidate. All dynamic interfaces retained.
module ddr_recovery #(
    parameter DATA_WIDTH = 16,
    parameter AXI_ADDR_WIDTH = 32,
    parameter AXI_LEN_WIDTH = 32,
    parameter AXI_DATA_WIDTH = 128,
    parameter CAM_DATA_LEN = 172800,
    parameter DEVICE = "PG"
)(
    input axi_clk,
    input axi_rst,
    input dma_abort,
    input transport_abort,
    output dma_abort_req,
    output [15:0] axi_data_available,
    input dma_done,
    input axi_cam_en,
    input [AXI_ADDR_WIDTH-1:0] cam_data_addr_1,
    input [AXI_ADDR_WIDTH-1:0] cam_data_addr_2,
    input [$clog2(CAM_DATA_LEN):0] cam_data_len,
    input [DATA_WIDTH-1:0] s_data /*synthesis PAP_MARK_DEBUG="1"*/,
    input s_data_valid /*synthesis PAP_MARK_DEBUG="1"*/,
    input s_hsync /*synthesis PAP_MARK_DEBUG="1"*/,
    input s_vsync /*synthesis PAP_MARK_DEBUG="1"*/,
    output [AXI_DATA_WIDTH-1:0] axi_data /*synthesis PAP_MARK_DEBUG="1"*/,
    output axi_data_valid /*synthesis PAP_MARK_DEBUG="1"*/,
    output axi_data_last /*synthesis PAP_MARK_DEBUG="1"*/,
    input axi_data_ready /*synthesis PAP_MARK_DEBUG="1"*/,
    output [AXI_ADDR_WIDTH-1:0] axi_cmd_addr /*synthesis PAP_MARK_DEBUG="1"*/,
    output [AXI_LEN_WIDTH-1:0] axi_cmd_len /*synthesis PAP_MARK_DEBUG="1"*/,
    output axi_cmd_valid /*synthesis PAP_MARK_DEBUG="1"*/,
    input axi_cmd_ready /*synthesis PAP_MARK_DEBUG="1"*/,
    output [1:0] xdma_req,
    output reg [31:0] dbg_fault_snapshot,
    output [31:0] dbg_reject_counts,
    output reg [31:0] dbg_input_pixels,
    output [31:0] dbg_axi_cnt,
    output [31:0] dbg_axi_num,
    output [31:0] dbg_zdin,
    output [31:0] dbg_zout,
    output [31:0] dbg_state,
    output [31:0] dbg_last_cnt,
    output [31:0] dbg_wd_cnt,
    input [1:0] xdma_ack,
    output [AXI_ADDR_WIDTH-1:0] prev_frame_base
);
    wire [DATA_WIDTH-1:0] m_data /*synthesis PAP_MARK_DEBUG="1"*/;
    wire m_data_valid /*synthesis PAP_MARK_DEBUG="1"*/;
    wire m_hsync /*synthesis PAP_MARK_DEBUG="1"*/;
    wire m_vsync /*synthesis PAP_MARK_DEBUG="1"*/;
    wire [AXI_DATA_WIDTH-1:0] w_data;
    wire [15:0] w_available;
    wire w_valid;
    wire w_last;
    wire w_ready;
    wire frame_active;
    wire tag_active;
    wire [AXI_DATA_WIDTH-1:0] tag_data;
    wire engine_busy;
    wire w_ping_o;
reg [2:0] flush_count;
wire capture_flush = (flush_count != 0);
reg capture_open, capture_bad;
reg [31:0] pixel_count, pixel_limit;
reg raw_vsync_q;
wire raw_sof = s_vsync && !raw_vsync_q;
wire capture_overflow;
wire capture_complete = capture_open && (pixel_count == pixel_limit);
wire frame_good = capture_complete && !capture_bad && !capture_overflow && !transport_abort;
wire capture_stop = capture_flush || capture_bad || capture_complete || transport_abort;
assign dma_abort_req = capture_bad | transport_abort;
reg [15:0] diag_overflows, diag_shorts;
reg [31:0] diag_input_count;
wire diag_short = raw_sof && !capture_complete;
wire diag_fault = capture_open && !capture_flush && !capture_bad &&
                  !m_vsync && (capture_overflow || diag_short);
assign dbg_reject_counts = {diag_overflows, diag_shorts};
always @(posedge axi_clk) begin
    if(axi_rst) begin
        dbg_fault_snapshot <= 0;
        diag_overflows <= 0;
        diag_shorts <= 0;
        diag_input_count <= 0;
        dbg_input_pixels <= 0;
    end else begin
        if(raw_sof) begin
            dbg_input_pixels <= diag_input_count;
            diag_input_count <= s_data_valid ? 1 : 0;
        end else if(s_data_valid) diag_input_count <= diag_input_count + 1'b1;
        if(diag_fault) begin
            dbg_fault_snapshot <= {capture_overflow, diag_short, 1'b0,
                                   !frame_active, pixel_count[27:0]};
            if(capture_overflow) diag_overflows <= diag_overflows + 1'b1;
            if(diag_short) diag_shorts <= diag_shorts + 1'b1;
        end else if(dma_abort && !capture_bad) begin
            dbg_fault_snapshot <= {2'b00, 1'b1, !frame_active, pixel_count[27:0]};
        end
    end
end
always @(posedge axi_clk) begin
    if(axi_rst) begin
        flush_count <= 4;
        raw_vsync_q <= 0;
    end else begin
        raw_vsync_q <= s_vsync;
        if(transport_abort || dma_abort || (dma_done && (!frame_active || !frame_good))) flush_count <= 4;
        else if(capture_flush) flush_count <= flush_count - 1'b1;
    end
end
always @(posedge axi_clk) begin
    if(axi_rst || capture_flush) begin
        capture_open <= 0;
        capture_bad <= 0;
        pixel_limit <= 0;
    end else if(m_vsync) begin
        capture_open <= 1;
        capture_bad <= (cam_data_len == 0);
        pixel_limit <= (cam_data_len * AXI_DATA_WIDTH) / DATA_WIDTH;
    end else if(capture_open) begin
        if(capture_overflow || (raw_sof && !capture_complete)) capture_bad <= 1;
    end
end
// Same reset/flush/admitted-SOF priority and modulo-2^32 increment.
// No shared conditional adder enable; each bit receives data every clock.
wire pixel_clear_tc04 = axi_rst || capture_flush || m_vsync;
wire pixel_step_tc04 = capture_open && m_data_valid;
genvar pixel_bit_tc04;
generate for(pixel_bit_tc04=0; pixel_bit_tc04<32; pixel_bit_tc04=pixel_bit_tc04+1) begin: pixel_d_tc04
    wire carry_tc04;
    if(pixel_bit_tc04==0) begin: low_bit
        assign carry_tc04 = pixel_step_tc04;
    end else begin: upper_bit
        assign carry_tc04 = pixel_step_tc04 && (&pixel_count[pixel_bit_tc04-1:0]);
    end
    always @(posedge axi_clk)
        pixel_count[pixel_bit_tc04] <= (pixel_count[pixel_bit_tc04] ^ carry_tc04) & !pixel_clear_tc04;
end endgenerate
ov5640_ddr_w_en #(.DATA_WIDTH(DATA_WIDTH)) ov5640_ddr_w_en(
    .capture_stop(capture_stop), .engine_busy(engine_busy | capture_flush | transport_abort),
    .axi_clk(axi_clk), .axi_rst(axi_rst), .axi_cam_en(axi_cam_en), .frame_pending(xdma_req),
    .s_data(s_data), .s_data_valid(s_data_valid), .s_hsync(s_hsync), .s_vsync(s_vsync),
    .m_data(m_data), .m_data_valid(m_data_valid), .m_hsync(m_hsync), .m_vsync(m_vsync)
);
ov5640_ddr_w #(
    .DATA_WIDTH(DATA_WIDTH), .AXI_DATA_WIDTH(AXI_DATA_WIDTH), .CAM_DATA_LEN(CAM_DATA_LEN), .DEVICE(DEVICE)
) ov5640_ddr_w(
    .axi_clk(axi_clk), .axi_rst(axi_rst), .capture_flush(capture_flush), .capture_overflow(capture_overflow),
    .axi_data_available(w_available), .data_len(cam_data_len),
    .s_data(m_data), .s_data_valid(m_data_valid), .s_hsync(m_hsync), .s_vsync(m_vsync),
    .axi_data(w_data), .axi_data_valid(w_valid), .axi_data_last(w_last), .axi_data_ready(w_ready),
    .dbg_axi_cnt(dbg_axi_cnt), .dbg_axi_num(dbg_axi_num), .dbg_zdin(dbg_zdin), .dbg_zout(dbg_zout)
);
assign axi_data_available = tag_active ? 16'd1 : (frame_active ? w_available : 16'd0);
assign axi_data = tag_active ? tag_data : w_data;
assign axi_data_valid = tag_active | (frame_active & w_valid);
assign axi_data_last = w_last;
assign w_ready = axi_data_ready & frame_active;
ddr_ctrl_recovery #(
    .AXI_ADDR_WIDTH(AXI_ADDR_WIDTH), .AXI_LEN_WIDTH(AXI_LEN_WIDTH),
    .AXI_DATA_WIDTH(AXI_DATA_WIDTH), .CAM_DATA_LEN(CAM_DATA_LEN)
) ov5640_ddr_w_ctrl(
    .axi_clk(axi_clk), .axi_rst(axi_rst),
    .cam_data_addr_1(cam_data_addr_1), .cam_data_addr_2(cam_data_addr_2), .cam_data_len(cam_data_len),
    .s_vsync(m_vsync), .dma_abort(dma_abort | transport_abort), .frame_good(frame_good), .dma_done(dma_done),
    .axi_cmd_addr(axi_cmd_addr), .axi_cmd_len(axi_cmd_len), .axi_cmd_valid(axi_cmd_valid), .axi_cmd_ready(axi_cmd_ready),
    .frame_active(frame_active), .tag_active(tag_active), .tag_data(tag_data), .tag_ready(axi_data_ready),
    .engine_busy(engine_busy), .w_ping_o(w_ping_o), .dbg_state(dbg_state), .dbg_last_cnt(dbg_last_cnt),
    .dbg_wd_cnt(dbg_wd_cnt), .xdma_req(xdma_req), .xdma_ack(xdma_ack)
);
assign prev_frame_base = w_ping_o ? cam_data_addr_1 : cam_data_addr_2;
endmodule
