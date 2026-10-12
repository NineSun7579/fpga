`timescale 1ns/1ps
module merge_reset_top_candidate #(parameter DELAY=16'h2710)(
input cfg_clk, locked, input [1:0] config_done,
input a_clk, b_clk, mrg_clk,
output rstn_int, merge_req_n, a_rst_n, b_rst_n, o_rst_n);
reg  [15:0]                 rstn_1ms = 16'd0            ;
reg startup_ready = 1'b0;
    always @(posedge cfg_clk or negedge locked)
        if (!locked) startup_ready <= 1'b0;
        else startup_ready <= (rstn_1ms == DELAY);

    always @(posedge cfg_clk or negedge locked)
    begin
    	if(!locked)
    	    rstn_1ms <= 16'd0;
    	else
    	begin
    		if(rstn_1ms == DELAY)
    		    rstn_1ms <= rstn_1ms;
    		else
    		    rstn_1ms <= rstn_1ms + 1'b1;
    	end
    end

    assign rstn_int  = locked & startup_ready;
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
assign a_rst_n=merge_a_sync[1];
assign b_rst_n=merge_b_sync[1];
assign o_rst_n=merge_o_sync[1];
endmodule
module production_sys_reset(input sys_clk, rstn_int, output sys_rst_n);
(* ASYNC_REG = "TRUE" *) reg [1:0] sys_rst_sync = 2'b00;
    always @(posedge sys_clk or negedge rstn_int)
        if (!rstn_int) sys_rst_sync <= 2'b00;
        else sys_rst_sync <= {sys_rst_sync[0], 1'b1};
    assign sys_rst_n = sys_rst_sync[1];
endmodule
module production_diag_reset(input clk_25M, rstn_int, output diag_rst_n);
(* ASYNC_REG = "TRUE" *) reg [1:0] diag_rst_sync = 2'b00;
    always @(posedge clk_25M or negedge rstn_int)
        if (!rstn_int) diag_rst_sync <= 2'b00;
        else diag_rst_sync <= {diag_rst_sync[0], 1'b1};
    assign diag_rst_n = diag_rst_sync[1];
endmodule
