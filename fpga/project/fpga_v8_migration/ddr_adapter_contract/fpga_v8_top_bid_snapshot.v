`timescale 1ns/1ps
// Exact arbiter-facing assignment from production top.v:524.
module fpga_v8_top_bid_snapshot (
    input wire [3:0] minted_bid,
    output wire [3:0] arb_s_bid,
    output wire [3:0] observed_minted_bid
);
    assign arb_s_bid = {3'b000, 1'b0};
    assign observed_minted_bid = minted_bid;
endmodule
