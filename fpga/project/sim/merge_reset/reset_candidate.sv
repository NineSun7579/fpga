`timescale 1ns/1ps
// Simulation-only extraction of the recommended TOP reset wiring.
// Production retains 16'h2710; the reduced value is only for the merge test.
module merge_reset_top_candidate # (parameter DELAY = 16'h2710) (
    input cfg_clk, locked, input [1:0] config_done,
    input a_clk, b_clk, mrg_clk,
    output rstn_int, merge_req_n, a_rst_n, b_rst_n, o_rst_n
);
    reg [15:0] rstn_1ms = 16'd0;
    always @(posedge cfg_clk or negedge locked)
        if (!locked) rstn_1ms <= 16'd0;
        else if (rstn_1ms != DELAY) rstn_1ms <= rstn_1ms + 1'b1;
    assign rstn_int = locked & (rstn_1ms == DELAY);
    assign merge_req_n = rstn_int & (&config_done);
    reg [1:0] merge_a_sync = 2'b00;
    reg [1:0] merge_b_sync = 2'b00;
    reg [1:0] merge_o_sync = 2'b00;
    always @(posedge a_clk or negedge merge_req_n)
        if (!merge_req_n) merge_a_sync <= 2'b00;
        else merge_a_sync <= {merge_a_sync[0], 1'b1};
    always @(posedge b_clk or negedge merge_req_n)
        if (!merge_req_n) merge_b_sync <= 2'b00;
        else merge_b_sync <= {merge_b_sync[0], 1'b1};
    always @(posedge mrg_clk or negedge merge_req_n)
        if (!merge_req_n) merge_o_sync <= 2'b00;
        else merge_o_sync <= {merge_o_sync[0], 1'b1};
    assign a_rst_n = merge_a_sync[1];
    assign b_rst_n = merge_b_sync[1];
    assign o_rst_n = merge_o_sync[1];
endmodule
