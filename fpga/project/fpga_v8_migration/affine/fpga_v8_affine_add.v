// Standalone uint8 affine residual add / requantizer. Verilog-2001, ASCII.
// Q16 scales are ratios to the output scale, unsigned in the full 32-bit range.
// Lane 0 occupies bits [7:0]. Data, constants and last are sampled together
// only on s_valid && s_ready. A stalled output never uses live constants.
module fpga_v8_affine_add #(
    parameter integer LANES = 16
) (
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire [LANES*8-1:0]     s_data_a,
    input  wire [LANES*8-1:0]     s_data_b,
    input  wire                   s_valid,
    output wire                   s_ready,
    input  wire                   s_last,
    input  wire [31:0]            scale_a,
    input  wire [31:0]            scale_b,
    input  wire [7:0]             zp_a,
    input  wire [7:0]             zp_b,
    input  wire [7:0]             zp_out,
    output reg  [LANES*8-1:0]     m_data,
    output reg                    m_valid,
    input  wire                   m_ready,
    output reg                    m_last
);

    function [7:0] affine_byte;
        input [7:0] qa;
        input [7:0] qb;
        input [31:0] sa;
        input [31:0] sb;
        input [7:0] za;
        input [7:0] zb;
        input [7:0] zo;
        reg signed [8:0] da;
        reg signed [8:0] db;
        reg signed [32:0] ca;
        reg signed [32:0] cb;
        reg signed [41:0] pa;
        reg signed [41:0] pb;
        reg signed [42:0] sum;
        reg signed [42:0] rounded;
        begin
            // Zero-extend bytes before signed subtraction: range -255..255.
            // No input clamp: codes below the zero point represent negatives.
            da = $signed({1'b0, qa}) - $signed({1'b0, za});
            db = $signed({1'b0, qb}) - $signed({1'b0, zb});
            ca = $signed({1'b0, sa});
            cb = $signed({1'b0, sb});
            pa = da * ca;
            pb = db * cb;
            // Explicit signed widening avoids unsigned concatenation promotion.
            // 43 bits cover both full-scale products, output bias and rounding.
            sum = $signed({pa[41], pa}) + $signed({pb[41], pb})
                + $signed({19'b0, zo, 16'b0});
            // Arithmetic shift is floor division, including for negative sums.
            rounded = (sum + 43'sd32768) >>> 16;
            if (rounded < 43'sd0)
                affine_byte = 8'd0;
            else if (rounded > 43'sd255)
                affine_byte = 8'd255;
            else
                affine_byte = rounded[7:0];
        end
    endfunction

    integer lane;
    // One elastic register, accepting a replacement when the old word drains.
    assign s_ready = rst_n && (!m_valid || m_ready);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            m_data <= {LANES*8{1'b0}};
            m_valid <= 1'b0;
            m_last <= 1'b0;
        end else if (s_ready) begin
            m_valid <= s_valid;
            if (s_valid) begin
                for (lane = 0; lane < LANES; lane = lane + 1)
                    m_data[lane*8 +: 8] <= affine_byte(
                        s_data_a[lane*8 +: 8], s_data_b[lane*8 +: 8],
                        scale_a, scale_b, zp_a, zp_b, zp_out);
                m_last <= s_last;
            end
        end
    end
endmodule
