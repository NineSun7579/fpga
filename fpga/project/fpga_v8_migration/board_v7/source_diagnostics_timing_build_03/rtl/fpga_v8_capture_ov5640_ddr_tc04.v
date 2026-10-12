// Isolated V5 capture wrapper; original w_* engines and public timing retained.
module fpga_v8_capture_ov5640_ddr_tc04 #(
    parameter DATA_WIDTH = 16,
    parameter AXI_DATA_WIDTH = 128,
    parameter CAM_DATA_LEN = 38400,
    parameter [31:0] BANK0_ADDR = 32'h01800000,
    parameter [31:0] BANK1_ADDR = 32'h01a00000,
    parameter DEVICE = "PG"
)(
    input axi_clk, input axi_rst, input epoch_start, input lease_block,
    input dma_abort, output dma_abort_req, input dma_done,
    output [15:0] axi_data_available, input axi_cam_en,
    input [DATA_WIDTH-1:0] s_data, input s_data_valid, input s_hsync, input s_vsync,
    output [AXI_DATA_WIDTH-1:0] axi_data,
    output axi_data_valid, output axi_data_last, input axi_data_ready,
    output [31:0] axi_cmd_addr, output [31:0] axi_cmd_len,
    output axi_cmd_valid, input axi_cmd_ready,
    output [1:0] xdma_req, input [1:0] xdma_ack,
    output admitted_sof, output capture_bank, output publish,
    output [31:0] publish_seq, output retired_error, output engine_idle,
    output capture_flush_o, output frame_good_o, output capture_overflow_o,
    output reg [31:0] dbg_fault_snapshot, output [31:0] dbg_reject_counts,
    output reg [31:0] dbg_input_pixels, output [31:0] dbg_axi_cnt,
    output [31:0] dbg_axi_num, output [31:0] dbg_zdin, output [31:0] dbg_zout,
    output [31:0] dbg_state, output [31:0] dbg_last_cnt, output [31:0] dbg_wd_cnt
);
    wire camera_rst = axi_rst | epoch_start;
    localparam LEN_WIDTH = $clog2(CAM_DATA_LEN)+1;
    localparam [LEN_WIDTH-1:0] cam_data_len = CAM_DATA_LEN;
    wire [DATA_WIDTH-1:0] m_data;
    wire m_data_valid, m_hsync, m_vsync;
    wire [AXI_DATA_WIDTH-1:0] w_data, tag_data;
    wire [15:0] w_available;
    wire w_valid, w_last, w_ready, frame_active, tag_active, engine_busy, w_ping_o;
    reg [2:0] flush_count;
    wire capture_flush = flush_count != 0;
    reg capture_open, capture_bad;
    reg [31:0] pixel_count, pixel_limit;
    reg raw_vsync_q;
    wire raw_sof = s_vsync && !raw_vsync_q;
    wire capture_overflow;
    wire capture_complete = capture_open && pixel_count == pixel_limit;
    wire frame_good = capture_complete && !capture_bad && !capture_overflow;
    wire capture_stop = capture_flush || capture_bad || capture_complete;
    assign dma_abort_req = capture_bad;
    assign admitted_sof = m_vsync;
    assign capture_bank = w_ping_o;
    assign publish = dma_done && dbg_state[2:0] == 3'd6 && frame_good && !dma_abort;
    assign publish_seq = dbg_last_cnt + 32'd1;
    assign retired_error = dma_abort || (dma_done && frame_active && !frame_good);
    assign engine_idle = !engine_busy && !capture_flush && !m_vsync;
    assign capture_flush_o = capture_flush;
    assign frame_good_o = frame_good;
    assign capture_overflow_o = capture_overflow;
    reg [15:0] diag_overflows, diag_shorts;
    reg [31:0] diag_input_count;
    wire diag_short = raw_sof && !capture_complete;
    wire diag_fault = capture_open && !capture_flush && !capture_bad &&
                      !m_vsync && (capture_overflow || diag_short);
    assign dbg_reject_counts = {diag_overflows, diag_shorts};
    always @(posedge axi_clk) begin
        if (camera_rst) begin
            dbg_fault_snapshot <= 0;
            diag_overflows <= 0;
            diag_shorts <= 0;
            diag_input_count <= 0;
            dbg_input_pixels <= 0;
        end else begin
            if (raw_sof) begin
                dbg_input_pixels <= diag_input_count;
                diag_input_count <= s_data_valid ? 1 : 0;
            end else if (s_data_valid) diag_input_count <= diag_input_count + 1'b1;
            if (diag_fault) begin
                dbg_fault_snapshot <= {capture_overflow, diag_short, 1'b0,
                                      !frame_active, pixel_count[27:0]};
                if (capture_overflow) diag_overflows <= diag_overflows + 1'b1;
                if (diag_short) diag_shorts <= diag_shorts + 1'b1;
            end else if (dma_abort && !capture_bad)
                dbg_fault_snapshot <= {2'b00, 1'b1, !frame_active, pixel_count[27:0]};
        end
    end
    always @(posedge axi_clk) begin
        if (camera_rst) begin flush_count <= 4; raw_vsync_q <= 0; end
        else begin
            raw_vsync_q <= s_vsync;
            if (dma_abort || (dma_done && (!frame_active || !frame_good))) flush_count <= 4;
            else if (capture_flush) flush_count <= flush_count - 1'b1;
        end
    end
    // Full 32-bit modulo increment. The enable is in each bit's data XOR,
    // not a shared CE propagated serially through eight register clusters.
    genvar pb;
    generate for (pb=0; pb<32; pb=pb+1) begin : g_pixel_count
        wire carry;
        if (pb == 0) assign carry = 1'b1;
        else assign carry = &pixel_count[pb-1:0];
        always @(posedge axi_clk) begin
            pixel_count[pb] <= (pixel_count[pb] ^ (capture_open && m_data_valid && carry)) &
                              !(camera_rst || capture_flush || m_vsync);
        end
    end endgenerate
    always @(posedge axi_clk) begin
        if (camera_rst || capture_flush) begin
            capture_open <= 0; capture_bad <= 0; pixel_limit <= 0;
        end else if (m_vsync) begin
            capture_open <= 1;
            capture_bad <= cam_data_len == 0;
            pixel_limit <= (cam_data_len * AXI_DATA_WIDTH) / DATA_WIDTH;
        end else if (capture_open) begin
            if (capture_overflow || (raw_sof && !capture_complete)) capture_bad <= 1;
        end
    end
    ov5640_ddr_w_en #(.DATA_WIDTH(DATA_WIDTH)) ov5640_ddr_w_en (
        .capture_stop(capture_stop),
        .engine_busy(engine_busy | capture_flush | lease_block |
                     (DATA_WIDTH != 16) | (AXI_DATA_WIDTH != 128)),
        .axi_clk(axi_clk), .axi_rst(camera_rst), .axi_cam_en(axi_cam_en),
        .frame_pending(xdma_req), .s_data(s_data), .s_data_valid(s_data_valid),
        .s_hsync(s_hsync), .s_vsync(s_vsync), .m_data(m_data),
        .m_data_valid(m_data_valid), .m_hsync(m_hsync), .m_vsync(m_vsync)
    );
    ov5640_ddr_w #(.DATA_WIDTH(DATA_WIDTH), .AXI_DATA_WIDTH(AXI_DATA_WIDTH),
        .CAM_DATA_LEN(CAM_DATA_LEN), .DEVICE(DEVICE)) ov5640_ddr_w (
        .axi_clk(axi_clk), .axi_rst(camera_rst), .capture_flush(capture_flush),
        .capture_overflow(capture_overflow), .axi_data_available(w_available),
        .data_len(cam_data_len), .s_data(m_data), .s_data_valid(m_data_valid),
        .s_hsync(m_hsync), .s_vsync(m_vsync), .axi_data(w_data),
        .axi_data_valid(w_valid), .axi_data_last(w_last), .axi_data_ready(w_ready),
        .dbg_axi_cnt(dbg_axi_cnt), .dbg_axi_num(dbg_axi_num),
        .dbg_zdin(dbg_zdin), .dbg_zout(dbg_zout)
    );
    assign axi_data_available = tag_active ? 16'd1 : (frame_active ? w_available : 16'd0);
    assign axi_data = tag_active ? tag_data : w_data;
    assign axi_data_valid = tag_active | (frame_active & w_valid);
    assign axi_data_last = w_last;
    assign w_ready = axi_data_ready & frame_active;
    ov5640_ddr_w_ctrl #(.AXI_ADDR_WIDTH(32), .AXI_LEN_WIDTH(32),
        .AXI_DATA_WIDTH(AXI_DATA_WIDTH), .CAM_DATA_LEN(CAM_DATA_LEN)) ov5640_ddr_w_ctrl (
        .axi_clk(axi_clk), .axi_rst(camera_rst), .cam_data_addr_1(BANK0_ADDR),
        .cam_data_addr_2(BANK1_ADDR), .cam_data_len(cam_data_len), .s_vsync(m_vsync),
        .dma_abort(dma_abort), .frame_good(frame_good), .dma_done(dma_done),
        .axi_cmd_addr(axi_cmd_addr), .axi_cmd_len(axi_cmd_len),
        .axi_cmd_valid(axi_cmd_valid), .axi_cmd_ready(axi_cmd_ready),
        .frame_active(frame_active), .tag_active(tag_active), .tag_data(tag_data),
        .tag_ready(axi_data_ready), .engine_busy(engine_busy), .w_ping_o(w_ping_o),
        .dbg_state(dbg_state), .dbg_last_cnt(dbg_last_cnt), .dbg_wd_cnt(dbg_wd_cnt),
        .xdma_req(xdma_req), .xdma_ack(xdma_ack)
    );
endmodule
