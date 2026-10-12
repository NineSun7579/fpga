
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
// Filename: ipsxe_fir_onboard_top.v
//////////////////////////////////////////////////////////////////////////////
`timescale 1ns/1ps
module ipsxe_fir_onboard_top
(
     i_clk       ,
     i_rstn      ,
     o_chk_err   ,
     o_chk_over  ,
     o_signal
);

localparam INPUT_WIDTH = 8; 

localparam COEF_WIDTH = 8;

localparam COEF_SUM = 4; 

localparam OUTPUT_WIDTH = 16; 

localparam FILTER_TYPE          = "Single Rate" ; 

localparam COEF_STRUCTURE       = "Even Symmetric" ;

localparam CFG_WIDTH = 8;
//end of tmp variable

input   i_clk;
input   i_rstn;
output  o_chk_err;
output  o_chk_over;
output  o_signal;

wire [INPUT_WIDTH-1:0] data_to_core;
wire                   data_last_to_core;
wire                   data_ready_from_core;
wire                   data_valid_to_core;

wire [OUTPUT_WIDTH-1:0] data_from_core;
wire                    data_last_from_core;
wire                    data_valid_from_core;

assign o_signal = |data_from_core;
//i_rstn debounce and sync to i_clk  
wire s_rstn;
ipsxe_fir_cross_sync_v1_0 #(
    .RST_CNTR_WIDTH(8'h10), 
    .RST_CNTR_VALUE(16'hc000)
) i_rstn_debounce (
    .clk(i_clk), 
    .rstn_in(i_rstn),  
    .rstn_out(s_rstn)
);

FIR u_FIR (
    .i_clk(i_clk),                          
    .i_rstn(s_rstn),                       
    .i_axi4s_data_tdata(data_to_core),         
    .i_axi4s_data_tlast(data_last_to_core),    
    .o_axi4s_data_tready(data_ready_from_core),  
    .i_axi4s_data_tvalid(data_valid_to_core),

    .o_axi4s_data_tdata(data_from_core),        
    .o_axi4s_data_tlast(data_last_from_core),   
    .i_axi4s_data_tready(1'b1), 
    .o_axi4s_data_tvalid(data_valid_from_core)  
);

ipsxe_fir_frame_gen #(
    .INPUT_WIDTH(INPUT_WIDTH),
    .COEF_WIDTH(COEF_WIDTH),
    .CFG_WIDTH(CFG_WIDTH),
    .COEF_SUM(COEF_SUM)
) u_ipsxe_fir_frame_gen (
    .i_clk(i_clk),                          
    .i_rstn(s_rstn),                       
    .o_axi4s_data_tdata(data_to_core),         
    .o_axi4s_data_tlast(data_last_to_core),    
    .i_axi4s_data_tready(data_ready_from_core),  
    .o_axi4s_data_tvalid(data_valid_to_core),

    .o_axi4s_reload_tdata(),
    .o_axi4s_reload_tlast(), 
    .i_axi4s_reload_tready(1'b0), 
    .o_axi4s_reload_tvalid(), 

    .o_axi4s_cfg_tdata(),     
    .i_axi4s_cfg_tready(1'b0),    
    .o_axi4s_cfg_tvalid()

);

ipsxe_fir_frame_chk #(
    .DATA_WIDTH(OUTPUT_WIDTH), 
    .FILTER_TYPE(FILTER_TYPE),

    .COEF_STRUCTURE(COEF_STRUCTURE)
) u_ipsxe_fir_frame_chk (
    .i_clk(i_clk),                          
    .i_rstn(s_rstn),                       
    .i_axi4s_data_tdata(data_from_core),         
    .i_axi4s_data_tlast(data_last_from_core),    
    .i_axi4s_data_tvalid(data_valid_from_core),
    .o_chk_over(o_chk_over),
    .o_chk_err(o_chk_err)
);

endmodule
