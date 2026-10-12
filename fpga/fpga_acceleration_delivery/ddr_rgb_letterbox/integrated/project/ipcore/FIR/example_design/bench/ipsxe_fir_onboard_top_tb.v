//////////////////////////////////////////////////////////////////////////////
//
// Copyright (c) 2022 PANGO MICROSYSTEMS, INC
// ALL RIGHTS REVERVED.
//
// THE SOURCE CODE CONTAINED HEREIN IS PROPRIETARY TO PANGO MICROSYSTEMS, INC.
// IT SHALL NOT BE REPRODUCED OR DISCLOSED IN WHOLE OR IN PART OR USED BY
// PARTIES WITHOUT WRITTEN AUTHORIZATION FROM THE OWNER.
//
//////////////////////////////////////////////////////////////////////////////

`timescale 1ns / 1ps
module ipsxe_fir_onboard_top_tb;

localparam CLK_PERIOD = 10;

reg   clk;
reg   rstn;
wire  chk_err;
wire  chk_over;
wire  signal;

initial
begin
    clk = 1'b0;
    rstn = 1'b0;
    #100;
    rstn = 1'b1;
    $display("Simulation Start...");
    wait(chk_over)
    #1000;
    if(chk_err)
        $display("Simulation is failed.");
    else
        $display("Simulation is successful.");
    $display("Simulation End...");
    $finish;
end

always #(CLK_PERIOD/2) clk = ~clk;

GTP_GRS GRS_INST( .GRS_N(1'b1) );

ipsxe_fir_onboard_top u_ipsxe_fir_onboard_top (
    .i_clk(clk),
    .i_rstn(rstn),
    .o_chk_err(chk_err),
    .o_chk_over(chk_over),
    .o_signal(signal)
);

endmodule
