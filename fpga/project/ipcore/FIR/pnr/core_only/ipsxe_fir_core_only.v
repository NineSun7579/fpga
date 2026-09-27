
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
// Filename: ipsxe_fir_core_only.v
//////////////////////////////////////////////////////////////////////////////
`timescale 1ns/1ps
module ipsxe_fir_core_only
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

localparam INPUT_WIDTH = 8; 

localparam COEF_WIDTH = 8;

localparam OUTPUT_WIDTH = 16; 

localparam CFG_WIDTH = 8;
//end of tmp variable

input  i_clk                 ;
input  i_rstn                ;
input  i_axi4s_data_tdata    ;
input  i_axi4s_data_tlast    ;
output o_axi4s_data_tready   ;
input  i_axi4s_data_tvalid   ;

output o_axi4s_data_tdata    ;
output o_axi4s_data_tlast    ;
input  i_axi4s_data_tready   ;
output o_axi4s_data_tvalid   ;

reg [INPUT_WIDTH-1:0] data_to_core;
wire [OUTPUT_WIDTH-1:0] data_from_core;

assign o_axi4s_data_tdata = |data_from_core;

always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        data_to_core <= {INPUT_WIDTH{1'b0}};
    else
        data_to_core <= {data_to_core[INPUT_WIDTH-1:1],i_axi4s_data_tdata};
end
FIR u_FIR (
    .i_clk(i_clk),                          
    .i_rstn(i_rstn),                       
    .i_axi4s_data_tdata(data_to_core),         
    .i_axi4s_data_tlast(i_axi4s_data_tlast),    
    .o_axi4s_data_tready(o_axi4s_data_tready),  
    .i_axi4s_data_tvalid(i_axi4s_data_tvalid),

    .o_axi4s_data_tdata(data_from_core),        
    .o_axi4s_data_tlast(o_axi4s_data_tlast),   
    .i_axi4s_data_tready(i_axi4s_data_tready), 
    .o_axi4s_data_tvalid(o_axi4s_data_tvalid)  
);

endmodule
