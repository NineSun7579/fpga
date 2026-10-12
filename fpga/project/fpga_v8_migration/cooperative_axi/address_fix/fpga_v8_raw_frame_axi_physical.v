`timescale 1ns/1ps
// Staged physical-address correction. Original bridge stays frozen for PDS.
// Reset outstanding AXI with the bus/slave. Publish only on done && !error.
module fpga_v8_raw_frame_axi_physical #(
    parameter integer WIDTH = 640,
    parameter integer HEIGHT = 480,
    parameter integer OUT_HEIGHT = 640,
    parameter integer TOP_ROWS = 80,
    parameter integer FILL_VALUE = 114,
    parameter integer ID_WIDTH = 4,
    parameter [ID_WIDTH-1:0] AXI_ID = 1,
    parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000
) (
    input wire clk,
    input wire rst_n,
    input wire cmd_valid,
    output wire cmd_ready,
    input wire [31:0] cmd_src_addr,
    input wire [31:0] cmd_dst_addr,
    input wire [31:0] cmd_frame_id,
    output reg cmd_error,
    output reg busy,
    output reg done,
    output reg error,
    output reg [31:0] active_src_addr,
    output reg [31:0] active_dst_addr,
    output reg [31:0] active_frame_id,
    output reg [31:0] completed_frame_id,

    output wire [ID_WIDTH-1:0] m_axi_read_arid,
    output wire [31:0] m_axi_read_araddr,
    output wire [7:0] m_axi_read_arlen,
    output wire [2:0] m_axi_read_arsize,
    output wire [1:0] m_axi_read_arburst,
    output wire m_axi_read_arlock,
    output wire [3:0] m_axi_read_arcache,
    output wire [2:0] m_axi_read_arprot,
    output wire [3:0] m_axi_read_arqos,
    output wire [3:0] m_axi_read_arregion,
    output wire m_axi_read_arvalid,
    input wire m_axi_read_arready,
    input wire [ID_WIDTH-1:0] m_axi_read_rid,
    input wire [127:0] m_axi_read_rdata,
    input wire [1:0] m_axi_read_rresp,
    input wire m_axi_read_rlast,
    input wire m_axi_read_rvalid,
    output wire m_axi_read_rready,

    output wire [ID_WIDTH-1:0] m_axi_write_awid,
    output wire [31:0] m_axi_write_awaddr,
    output wire [7:0] m_axi_write_awlen,
    output wire [2:0] m_axi_write_awsize,
    output wire [1:0] m_axi_write_awburst,
    output wire m_axi_write_awlock,
    output wire [3:0] m_axi_write_awcache,
    output wire [2:0] m_axi_write_awprot,
    output wire [3:0] m_axi_write_awqos,
    output wire [3:0] m_axi_write_awregion,
    output wire m_axi_write_awvalid,
    input wire m_axi_write_awready,
    output wire [127:0] m_axi_write_wdata,
    output wire [15:0] m_axi_write_wstrb,
    output wire m_axi_write_wlast,
    output wire m_axi_write_wvalid,
    input wire m_axi_write_wready,
    input wire [ID_WIDTH-1:0] m_axi_write_bid,
    input wire [1:0] m_axi_write_bresp,
    input wire m_axi_write_bvalid,
    output wire m_axi_write_bready
);
    // Wide arithmetic validates both real bytes and the full bus footprint.
    localparam [63:0] SRC_PIXELS = 64'd1 * WIDTH * HEIGHT;
    localparam [63:0] SRC_WORDS = (SRC_PIXELS * 2 + 15) / 16;
    localparam [63:0] DST_WORDS = (64'd3 * WIDTH * OUT_HEIGHT + 15) / 16;
    localparam [63:0] SRC_BUS_BYTES = SRC_WORDS * 16;
    localparam [63:0] DST_BUS_BYTES = DST_WORDS * 16;
    // Live top.v forwards only [27:0] to DDR; the 512 MiB decode aliases.
    localparam [63:0] DDR_LIMIT = {32'd0, DDR_ADDRESS_LIMIT};
    localparam CONFIG_OK = (WIDTH >= 1) && (WIDTH <= 65535) &&
                           (HEIGHT >= 1) && (HEIGHT <= 65535) &&
                           (OUT_HEIGHT >= HEIGHT) && (OUT_HEIGHT <= 65535) &&
                           (TOP_ROWS >= 0) && (TOP_ROWS <= OUT_HEIGHT - HEIGHT) &&
                           (FILL_VALUE >= 0) && (FILL_VALUE <= 255) &&
                           (ID_WIDTH >= 1) && (DDR_ADDRESS_LIMIT != 0) &&
                           (DDR_ADDRESS_LIMIT[3:0] == 0) &&
                           (DDR_ADDRESS_LIMIT <= 32'h10000000) &&
                           (SRC_BUS_BYTES <= DDR_LIMIT) &&
                           (DST_BUS_BYTES <= DDR_LIMIT);
    localparam [1:0] WR_IDLE = 2'd0, WR_AW = 2'd1,
                     WR_W = 2'd2, WR_B = 2'd3;

    wire [63:0] src_end = {32'd0, cmd_src_addr} + SRC_BUS_BYTES;
    wire [63:0] dst_end = {32'd0, cmd_dst_addr} + DST_BUS_BYTES;
    wire cmd_invalid = !CONFIG_OK || (cmd_src_addr[3:0] != 0) ||
                       (cmd_dst_addr[3:0] != 0) ||
                       (src_end > DDR_LIMIT) || (dst_end > DDR_LIMIT) ||
                       (src_end > 64'h100000000) || (dst_end > 64'h100000000) ||
                       (({32'd0, cmd_src_addr} < dst_end) &&
                        ({32'd0, cmd_dst_addr} < src_end));

    reg ar_valid;
    reg [31:0] read_addr;
    reg read_pending;
    reg [31:0] read_words_remaining;
    reg [31:0] source_pixels_remaining;
    reg [127:0] serial_data;
    reg [3:0] serial_count;
    reg serial_valid;
    reg reader_done;
    reg [1:0] write_state;
    reg [31:0] write_addr;
    reg [127:0] write_data;
    reg [15:0] write_keep;
    reg write_last;
    reg last_write_retired;

    wire raw_start_ready, raw_busy, raw_done, raw_error, raw_config_error;
    wire [23:0] rgb_data;
    wire rgb_valid, rgb_ready, rgb_last, source_ready;
    wire [127:0] packed_data;
    wire [15:0] packed_keep;
    wire packed_valid, packed_ready, packed_last;
    wire pipeline_idle = !raw_busy && !rgb_valid && !packed_valid;

    assign cmd_ready = rst_n && !busy && !ar_valid && !read_pending &&
                       !serial_valid && (write_state == WR_IDLE) && pipeline_idle;
    wire accept_cmd = cmd_valid && cmd_ready;
    wire raw_start = accept_cmd && !cmd_invalid;
    assign packed_ready = rst_n && busy && (write_state == WR_IDLE) &&
                          !last_write_retired;

    fpga_v8_raw_letterbox #(
        .WIDTH(WIDTH), .HEIGHT(HEIGHT), .OUT_HEIGHT(OUT_HEIGHT),
        .TOP_ROWS(TOP_ROWS), .FILL_VALUE(FILL_VALUE)
    ) raw_pipeline (
        .clk(clk), .rst_n(rst_n), .start_valid(raw_start),
        .start_ready(raw_start_ready), .busy(raw_busy), .done(raw_done),
        .frame_error(raw_error), .config_error(raw_config_error),
        .s_data(serial_data[15:0]), .s_valid(serial_valid),
        .s_ready(source_ready), .s_last(source_pixels_remaining == 1),
        .m_data(rgb_data), .m_valid(rgb_valid), .m_ready(rgb_ready),
        .m_last(rgb_last)
    );
    fpga_v8_rgb888_pack128 output_packer (
        .clk(clk), .rst_n(rst_n), .s_data(rgb_data), .s_valid(rgb_valid),
        .s_ready(rgb_ready), .s_last(rgb_last), .m_data(packed_data),
        .m_keep(packed_keep), .m_valid(packed_valid),
        .m_ready(packed_ready), .m_last(packed_last)
    );

    assign m_axi_read_arid = AXI_ID;
    assign m_axi_read_araddr = read_addr;
    assign m_axi_read_arlen = 8'd0;
    assign m_axi_read_arsize = 3'd4;
    assign m_axi_read_arburst = 2'b01;
    assign m_axi_read_arlock = 1'b0;
    assign m_axi_read_arcache = 4'h3;
    assign m_axi_read_arprot = 3'd0;
    assign m_axi_read_arqos = 4'd0;
    assign m_axi_read_arregion = 4'd0;
    assign m_axi_read_arvalid = rst_n && ar_valid;
    // An issued read always has a free serializer, so output padding never
    // keeps the DDR read response outstanding while RGB output is blocked.
    assign m_axi_read_rready = rst_n && busy && read_pending && !serial_valid;

    assign m_axi_write_awid = AXI_ID;
    assign m_axi_write_awaddr = write_addr;
    assign m_axi_write_awlen = 8'd0;
    assign m_axi_write_awsize = 3'd4;
    assign m_axi_write_awburst = 2'b01;
    assign m_axi_write_awlock = 1'b0;
    assign m_axi_write_awcache = 4'h3;
    assign m_axi_write_awprot = 3'd0;
    assign m_axi_write_awqos = 4'd0;
    assign m_axi_write_awregion = 4'd0;
    assign m_axi_write_awvalid = rst_n && busy && (write_state == WR_AW);
    assign m_axi_write_wdata = write_data;
    assign m_axi_write_wstrb = write_keep;
    assign m_axi_write_wlast = 1'b1;
    assign m_axi_write_wvalid = rst_n && busy && (write_state == WR_W);
    assign m_axi_write_bready = rst_n && busy && (write_state == WR_B);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cmd_error <= 1'b0;
            busy <= 1'b0;
            done <= 1'b0;
            error <= 1'b0;
            active_src_addr <= 32'd0;
            active_dst_addr <= 32'd0;
            active_frame_id <= 32'd0;
            completed_frame_id <= 32'd0;
            ar_valid <= 1'b0;
            read_addr <= 32'd0;
            read_pending <= 1'b0;
            read_words_remaining <= 32'd0;
            source_pixels_remaining <= 32'd0;
            serial_data <= 128'd0;
            serial_count <= 4'd0;
            serial_valid <= 1'b0;
            reader_done <= 1'b0;
            write_state <= WR_IDLE;
            write_addr <= 32'd0;
            write_data <= 128'd0;
            write_keep <= 16'd0;
            write_last <= 1'b0;
            last_write_retired <= 1'b0;
        end else begin
            cmd_error <= 1'b0;
            done <= 1'b0;
            if (accept_cmd) begin
                active_src_addr <= cmd_src_addr;
                active_dst_addr <= cmd_dst_addr;
                active_frame_id <= cmd_frame_id;
                error <= cmd_invalid;
                if (cmd_invalid) begin
                    cmd_error <= 1'b1;
                end else begin
                    busy <= 1'b1;
                    read_addr <= cmd_src_addr;
                    read_words_remaining <= SRC_WORDS[31:0];
                    source_pixels_remaining <= SRC_PIXELS[31:0];
                    serial_count <= 4'd0;
                    reader_done <= 1'b0;
                    write_addr <= cmd_dst_addr;
                    last_write_retired <= 1'b0;
                end
            end else if (busy) begin
                if (raw_error || raw_config_error)
                    error <= 1'b1;

                if (!ar_valid && !read_pending && !serial_valid &&
                    (read_words_remaining != 0))
                    ar_valid <= 1'b1;
                if (m_axi_read_arvalid && m_axi_read_arready) begin
                    ar_valid <= 1'b0;
                    read_pending <= 1'b1;
                    read_addr <= read_addr + 32'd16;
                    read_words_remaining <= read_words_remaining - 32'd1;
                end
                if (m_axi_read_rvalid && m_axi_read_rready) begin
                    read_pending <= 1'b0;
                    serial_data <= m_axi_read_rdata;
                    serial_count <= (source_pixels_remaining >= 8) ?
                                    4'd8 : source_pixels_remaining[3:0];
                    serial_valid <= 1'b1;
                    if ((m_axi_read_rid != AXI_ID) ||
                        (m_axi_read_rresp != 2'b00) || !m_axi_read_rlast)
                        error <= 1'b1;
                end
                if (serial_valid && source_ready) begin
                    serial_data <= {16'd0, serial_data[127:16]};
                    serial_count <= serial_count - 4'd1;
                    source_pixels_remaining <= source_pixels_remaining - 32'd1;
                    if (serial_count == 1)
                        serial_valid <= 1'b0;
                    if (source_pixels_remaining == 1)
                        reader_done <= 1'b1;
                end

                // AW is not requested until a complete packed beat exists.
                // Accept AW, hold W through stalls, then wait for its B.
                case (write_state)
                    WR_IDLE: if (packed_valid && packed_ready) begin
                        write_data <= packed_data;
                        write_keep <= packed_keep;
                        write_last <= packed_last;
                        write_state <= WR_AW;
                    end
                    WR_AW: if (m_axi_write_awready)
                        write_state <= WR_W;
                    WR_W: if (m_axi_write_wready)
                        write_state <= WR_B;
                    WR_B: if (m_axi_write_bvalid) begin
                        if ((m_axi_write_bid != AXI_ID) ||
                            (m_axi_write_bresp != 2'b00))
                            error <= 1'b1;
                        write_state <= WR_IDLE;
                        if (write_last)
                            last_write_retired <= 1'b1;
                        else
                            write_addr <= write_addr + 32'd16;
                    end
                endcase
                if (reader_done && last_write_retired && pipeline_idle &&
                    !ar_valid && !read_pending && !serial_valid &&
                    (write_state == WR_IDLE)) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                    completed_frame_id <= active_frame_id;
                end
            end
        end
    end
endmodule
