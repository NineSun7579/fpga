module pll56_source_drop_counter (
    input clk, input rst, input frame, input increment,
    output wire [31:0] value
);
    wire [31:0] sum = value + {31'd0, increment};
    wire [31:0] next_value = {sum[31:1] & {31{!frame}},
                              frame ? increment : sum[0]};
    genvar bit_index;
    generate for (bit_index=0; bit_index<32; bit_index=bit_index+1) begin: bits
        GTP_DFF_C #(.GRS_EN("TRUE"), .INIT(1'b0)) ff (
            .Q(value[bit_index]), .D(next_value[bit_index]), .CLK(clk), .C(rst)
        );
    end endgenerate
endmodule
module top(input clk, input rst, input frame, input increment,
output [31:0] value);
pll56_source_drop_counter u_src_drop(.clk(clk), .rst(rst), .frame(frame),
.increment(increment), .value(value));
endmodule
