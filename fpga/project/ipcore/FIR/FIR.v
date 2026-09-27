
//////////////////////////////////////////////////////////////////////////////
//
// Copyright (c) 2014 PANGO MICROSYSTEMS, INC
// ALL RIGHTS REVERVED.
//
// THE SOURCE CODE CONTAINED HEREIN IS PROPRIETARY TO PANGO MICROSYSTEMS, INC.
// IT SHALL NOT BE REPRODUCED OR DISCLOSED IN WHOLE OR IN PART OR USED BY
// PARTIES WITHOUT WRITTEN AUTHORIZATION FROM THE OWNER.
//
//////////////////////////////////////////////////////////////////////////////
//
// Library:
// Filename: FIR.v
//////////////////////////////////////////////////////////////////////////////
`timescale 1ns/1ps
module FIR
(
     i_clk                 ,
     i_rstn                ,
     //input data
     i_axi4s_data_tdata    ,
     i_axi4s_data_tlast    ,
     o_axi4s_data_tready   ,
     i_axi4s_data_tvalid   ,

     //output data
     o_axi4s_data_tdata    ,
     o_axi4s_data_tlast    ,
     i_axi4s_data_tready   ,
     o_axi4s_data_tvalid
);


localparam INPUT_WIDTH          = 6 ; 

localparam COEF_WIDTH           = 3 ; 

localparam COEF_SUM             = 4 ; 

localparam COEF_STRUCTURE       = "Even Symmetric" ;

localparam RELOAD_COEF          = 0 ; 

localparam OUTPUT_WIDTH         = 11 ; 

localparam OUTPUT_ROUNDING_MODE = "Full Precision" ; 

localparam FILTER_TYPE          = "Single Rate" ; 

//end of tmp variable
input                     i_clk                 ;
input                     i_rstn                ;
input  [INPUT_WIDTH-1:0]  i_axi4s_data_tdata    ;
input                     i_axi4s_data_tlast    ;
output                    o_axi4s_data_tready   ;
input                     i_axi4s_data_tvalid   ;

output [OUTPUT_WIDTH-1:0] o_axi4s_data_tdata    ;
output                    o_axi4s_data_tlast    ;
input                     i_axi4s_data_tready   ;
output                    o_axi4s_data_tvalid   ;

ipsxe_fir_core_v1_2_FIR
#(
    .INPUT_WIDTH(INPUT_WIDTH),
    .COEF_WIDTH(COEF_WIDTH),
    .COEF_SUM(COEF_SUM),
    .RELOAD_COEF(RELOAD_COEF),
	.OUTPUT_WIDTH(OUTPUT_WIDTH),
	.OUTPUT_ROUNDING_MODE(OUTPUT_ROUNDING_MODE),

    .COEF_STRUCTURE(COEF_STRUCTURE)
)u_ipsxe_fir_core_v1_2_FIR
(
    .i_clk(i_clk),
    .i_rstn( i_rstn),
    .i_axi4s_data_tdata(i_axi4s_data_tdata),
    .i_axi4s_data_tlast(i_axi4s_data_tlast),
    .o_axi4s_data_tready(o_axi4s_data_tready),
    .i_axi4s_data_tvalid(i_axi4s_data_tvalid),

    .o_axi4s_data_tdata(o_axi4s_data_tdata),
    .o_axi4s_data_tlast(o_axi4s_data_tlast),
    .i_axi4s_data_tready(i_axi4s_data_tready),
    .o_axi4s_data_tvalid(o_axi4s_data_tvalid)
);
endmodule
