// Isolated candidate convolution finish. ASCII, Verilog-2001, no vendor IP.
// Lane 0 is the least significant slice of each packed bus.
// Constants, bypass and last belong to the word accepted on s_valid/s_ready.
module fpga_v8_conv_finish #(
    parameter integer LANES = 16
) (
    input  wire                   clk,
    input  wire                   rst,
    input  wire [LANES*32-1:0]    s_data,
    input  wire                   s_valid,
    output wire                   s_ready,
    input  wire                   s_last,
    input  wire [15:0]            scale_q16,
    input  wire [LANES*32-1:0]    folded_bias_q16,
    input  wire [7:0]             preactivation_zero_point,
    input  wire                   bypass,
    input  wire                   cfg_valid,
    output wire                   cfg_ready,
    input  wire [7:0]             cfg_addr,
    input  wire [7:0]             cfg_data,
    output wire [LANES*8-1:0]     m_data,
    output wire                   m_valid,
    input  wire                   m_ready,
    output wire                   m_last
);
    reg product_valid;
    reg sum_valid;
    reg byte_valid;
    reg product_last;
    reg sum_last;
    reg byte_last;
    reg product_bypass;
    reg sum_bypass;
    reg byte_bypass;
    reg [7:0] product_zero_point;

    wire product_ready;
    wire sum_ready;
    wire byte_ready;
    wire input_fire;
    wire lut_s_ready;
    wire lut_cfg_ready;
    wire lut_cfg_valid;
    wire [LANES*8-1:0] byte_data;
    wire signed [16:0] positive_scale = $signed({1'b0, scale_q16});

    assign byte_ready = !byte_valid || lut_s_ready;
    assign sum_ready = !sum_valid || byte_ready;
    assign product_ready = !product_valid || sum_ready;
    // Configuration requests stop the source but allow existing words to drain.
    assign s_ready = !rst && !cfg_valid && product_ready;
    assign input_fire = s_valid && s_ready;
    // Reject writes while ANY register holds a word, including the LUT output.
    // The output consumption edge is still busy; programming starts next edge.
    assign cfg_ready = !rst && !product_valid && !sum_valid && !byte_valid
                     && lut_cfg_ready;
    assign lut_cfg_valid = cfg_valid && cfg_ready;

    function [7:0] saturate_q16;
        input signed [50:0] value;
        reg signed [50:0] rounded;
        begin
            // Arithmetic shift implements floor, including negative half ties.
            rounded = (value + 51'sd32768) >>> 16;
            if (rounded < 51'sd0)
                saturate_q16 = 8'd0;
            else if (rounded > 51'sd255)
                saturate_q16 = 8'd255;
            else
                saturate_q16 = rounded[7:0];
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            product_valid <= 1'b0;
            sum_valid <= 1'b0;
            byte_valid <= 1'b0;
            product_last <= 1'b0;
            sum_last <= 1'b0;
            byte_last <= 1'b0;
            product_bypass <= 1'b0;
            sum_bypass <= 1'b0;
            byte_bypass <= 1'b0;
            product_zero_point <= 8'd0;
        end else begin
            if (product_ready) begin
                product_valid <= input_fire;
                if (input_fire) begin
                    product_last <= s_last;
                    product_bypass <= bypass;
                    product_zero_point <= preactivation_zero_point;
                end
            end
            if (sum_ready) begin
                sum_valid <= product_valid;
                if (product_valid) begin
                    sum_last <= product_last;
                    sum_bypass <= product_bypass;
                end
            end
            if (byte_ready) begin
                byte_valid <= sum_valid;
                if (sum_valid) begin
                    byte_last <= sum_last;
                    byte_bypass <= sum_bypass;
                end
            end
        end
    end

    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin : lanes
            wire signed [31:0] accumulator = $signed(s_data[lane*32 +: 32]);
            // 32-bit signed times zero-extended 16-bit unsigned needs 49 bits.
            wire signed [48:0] multiply_value = accumulator * positive_scale;
            reg signed [50:0] product;
            reg signed [31:0] bias;
            reg signed [50:0] q16_sum;
            reg [7:0] code;
            assign byte_data[lane*8 +: 8] = code;
            always @(posedge clk) begin
                if (rst) begin
                    product <= 51'sd0;
                    bias <= 32'sd0;
                    q16_sum <= 51'sd0;
                    code <= 8'd0;
                end else begin
                    if (input_fire) begin
                        product <= $signed({{2{multiply_value[48]}}, multiply_value});
                        bias <= $signed(folded_bias_q16[lane*32 +: 32]);
                    end
                    if (sum_ready && product_valid) begin
                        // Explicit signed 51-bit operands avoid unsigned promotion.
                        q16_sum <= product + $signed({{19{bias[31]}}, bias})
                            + $signed({27'b0, product_zero_point, 16'b0});
                    end
                    if (byte_ready && sum_valid)
                        code <= saturate_q16(q16_sum);
                end
            end
        end
    endgenerate

    // Reuse the existing primitive; its bypass is driven by the matching word.
    fpga_v8_activation_lut #(.LANES(LANES)) activation (
        .clk(clk), .rst(rst),
        .cfg_valid(lut_cfg_valid), .cfg_ready(lut_cfg_ready),
        .cfg_addr(cfg_addr), .cfg_data(cfg_data),
        .s_valid(byte_valid), .s_ready(lut_s_ready),
        .s_data(byte_data), .s_last(byte_last), .bypass(byte_bypass),
        .m_valid(m_valid), .m_ready(m_ready), .m_data(m_data), .m_last(m_last)
    );
endmodule
