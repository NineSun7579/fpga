
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
// Filename: ipsxe_fir_frame_gen.v
//////////////////////////////////////////////////////////////////////////////
`timescale 1ns/1ps
module ipsxe_fir_frame_gen
#(
    parameter INPUT_WIDTH = 25,
    parameter COEF_WIDTH = 18, 
    parameter CFG_WIDTH = 8,
    parameter COEF_SUM = 16
)
(
     i_clk                 ,
     i_rstn                ,

     o_axi4s_data_tdata    ,
     o_axi4s_data_tlast    ,
     i_axi4s_data_tready   ,
     o_axi4s_data_tvalid   ,

     o_axi4s_reload_tdata  ,
     o_axi4s_reload_tlast  ,
     i_axi4s_reload_tready ,
     o_axi4s_reload_tvalid ,

     o_axi4s_cfg_tdata     ,
     i_axi4s_cfg_tready    ,
     o_axi4s_cfg_tvalid    
);

input                        i_clk                 ;
input                        i_rstn                ;

output reg [INPUT_WIDTH-1:0] o_axi4s_data_tdata    ;
output                       o_axi4s_data_tlast    ;
input                        i_axi4s_data_tready   ;
output reg                   o_axi4s_data_tvalid   ;

output reg [COEF_WIDTH-1:0]  o_axi4s_reload_tdata  ;
output                       o_axi4s_reload_tlast  ;
input                        i_axi4s_reload_tready ;
output reg                   o_axi4s_reload_tvalid ;

output     [CFG_WIDTH-1:0]   o_axi4s_cfg_tdata     ;
input                        i_axi4s_cfg_tready    ;
output reg                   o_axi4s_cfg_tvalid    ;

function integer clog2;
    input integer n;
    begin
        n = n - 1;
        for (clog2=0; n>0; clog2=clog2+1)
            n = n >> 1;
    end
endfunction

localparam DATA_SAMPLES = 1024;
localparam DATA_CNT_WIDTH = clog2(DATA_SAMPLES)+1; 
localparam COEF_CNT_WIDTH = clog2(COEF_SUM)+1; 

reg [DATA_CNT_WIDTH-1:0] data_cnt;
reg [COEF_CNT_WIDTH-1:0] coef_cnt;
reg reload_done;

//data generate
always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        o_axi4s_data_tvalid <= 1'b0;
    else if(o_axi4s_data_tlast == 1'b1)
        o_axi4s_data_tvalid <= 1'b0;
    else if(i_axi4s_data_tready == 1'b1 && data_cnt < DATA_SAMPLES)
        o_axi4s_data_tvalid <= 1'b1+o_axi4s_data_tvalid;
end

assign o_axi4s_data_tlast = o_axi4s_data_tvalid && data_cnt == DATA_SAMPLES-1;

always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        o_axi4s_data_tdata <= {(INPUT_WIDTH){1'b0}};
    else if(o_axi4s_data_tlast)
        o_axi4s_data_tdata <= {(INPUT_WIDTH){1'b0}};
    else if(o_axi4s_data_tvalid == 1'b1)
        o_axi4s_data_tdata <= o_axi4s_data_tdata + 1'b1;
end

always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        data_cnt <= {DATA_CNT_WIDTH{1'b0}};
    else if(o_axi4s_data_tvalid == 1'b1 && data_cnt < DATA_SAMPLES)
        data_cnt <= data_cnt + {{(DATA_CNT_WIDTH-1){1'b0}},1'b1};
end

//reload generate
always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        o_axi4s_reload_tvalid <= 1'b0;
    else if(o_axi4s_reload_tlast == 1'b1)
        o_axi4s_reload_tvalid <= 1'b0;
    else if(i_axi4s_reload_tready == 1'b1 && coef_cnt < COEF_SUM)
        o_axi4s_reload_tvalid <= 1'b1;
    end

assign o_axi4s_reload_tlast = o_axi4s_data_tvalid && coef_cnt == COEF_SUM-1;

always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        o_axi4s_reload_tdata <= {COEF_WIDTH{1'b0}};
    else 
        o_axi4s_reload_tdata <= {{(COEF_WIDTH-2){1'b0}},2'b10};
end

always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        coef_cnt <= {COEF_CNT_WIDTH{1'b0}};
    else if(o_axi4s_reload_tvalid == 1'b1 && coef_cnt < COEF_SUM)
        coef_cnt <= coef_cnt + {{(COEF_CNT_WIDTH-1){1'b0}},1'b1};
end

//cfg generate
always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        reload_done <= 1'b0;
    else if(o_axi4s_cfg_tvalid == 1'b1)
        reload_done <= 1'b0;
    else if(o_axi4s_reload_tlast == 1'b1)
        reload_done <= 1'b1;
    else
        reload_done <= 1'b0;
    end

always@(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        o_axi4s_cfg_tvalid <= 1'b0;
    else if(i_axi4s_cfg_tready == 1'b1 && reload_done == 1'b1)
        o_axi4s_cfg_tvalid <= 1'b1;
    else
        o_axi4s_cfg_tvalid <= 1'b0;
end

assign o_axi4s_cfg_tdata = {CFG_WIDTH{1'b0}};

endmodule
