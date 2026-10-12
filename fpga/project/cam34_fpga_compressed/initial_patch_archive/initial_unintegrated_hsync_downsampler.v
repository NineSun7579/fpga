`timescale 1ns/1ps
// C3/C4 FPGA-side 2x2 RGB565 reduction.
// Input: one accepted 640x480 pixel per in_valid, line/frame levels.
// Output: one 320x240 pixel on every odd source column of every odd source row.
// The output byte count is 320*240*2 = 153600, so RK3568 never reads the RAW frame.
module cam34_downsample_2x2 #(
    parameter integer IN_W = 640,
    parameter integer IN_H = 480
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        in_valid,
    input  wire [15:0] in_pixel,
    input  wire        in_hsync,
    input  wire        in_vsync,
    output reg         out_valid,
    output reg  [15:0] out_pixel,
    output wire        out_hsync,
    output wire        out_vsync
);
    localparam integer XW = (IN_W <= 2) ? 1 : $clog2(IN_W);
    localparam integer YW = (IN_H <= 2) ? 1 : $clog2(IN_H);
    localparam integer OUT_W = IN_W / 2;

    // Each entry stores the sum of two expanded 8-bit RGB channels for the
    // previous row's horizontal pair. 30 bits = 10 bits per channel.
    reg [29:0] line_sum [0:OUT_W-1];
    reg [15:0] prev_pixel;
    reg [XW:0] x_count;
    reg [YW:0] row_count;
    reg hsync_q, vsync_q, await_first_line;
    integer pair_index;
    reg [29:0] top_sum;
    reg [29:0] bottom_sum;

    assign out_hsync = in_hsync;
    assign out_vsync = in_vsync;

    function [9:0] r8;
        input [15:0] p;
        begin r8 = {p[15:11], p[15:13]}; end
    endfunction
    function [9:0] g8;
        input [15:0] p;
        begin g8 = {p[10:5], p[10:9]}; end
    endfunction
    function [9:0] b8;
        input [15:0] p;
        begin b8 = {p[4:0], p[4:2]}; end
    endfunction
    function [29:0] pair_sum_fn;
        input [15:0] a;
        input [15:0] b;
        begin
            pair_sum_fn = {r8(a)+r8(b), g8(a)+g8(b), b8(a)+b8(b)};
        end
    endfunction
    function [15:0] quad_avg_fn;
        input [29:0] top;
        input [29:0] bot;
        reg [11:0] rr, gg, bb;
        begin
            rr = (top[29:20] + bot[29:20] + 2) >> 2;
            gg = (top[19:10] + bot[19:10] + 2) >> 2;
            bb = (top[9:0]   + bot[9:0]   + 2) >> 2;
            quad_avg_fn = {rr[7:3], gg[7:2], bb[7:3]};
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            prev_pixel      <= 16'd0;
            x_count         <= 0;
            row_count       <= 0;
            hsync_q         <= 1'b0;
            vsync_q         <= 1'b0;
            await_first_line<= 1'b0;
            out_valid       <= 1'b0;
            out_pixel       <= 16'd0;
        end else begin
            out_valid <= 1'b0;
            hsync_q <= in_hsync;
            vsync_q <= in_vsync;

            if (in_vsync && !vsync_q) begin
                x_count <= 0;
                row_count <= 0;
                await_first_line <= 1'b1;
            end else if (in_hsync && !hsync_q) begin
                x_count <= 0;
                if (await_first_line) begin
                    row_count <= 0;
                    await_first_line <= 1'b0;
                end else begin
                    row_count <= row_count + 1'b1;
                end
            end

            if (in_valid) begin
                if (!x_count[0]) begin
                    prev_pixel <= in_pixel;
                end else begin
                    pair_index = x_count >> 1;
                    if (!row_count[0]) begin
                        line_sum[pair_index] <= pair_sum_fn(prev_pixel, in_pixel);
                    end else begin
                        top_sum = line_sum[pair_index];
                        bottom_sum = pair_sum_fn(prev_pixel, in_pixel);
                        out_pixel <= quad_avg_fn(top_sum, bottom_sum);
                        out_valid <= 1'b1;
                    end
                end
                x_count <= x_count + 1'b1;
            end
        end
    end
endmodule
