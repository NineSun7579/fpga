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
// Functional description: fft frame checker
// Note: The module only checkes the interface timing and doesn't check the frame data value.                                                          

module ipsxe_fir_frame_chk #(
    parameter DATA_WIDTH = 48              ,
    parameter FILTER_TYPE = "Single Rate"  ,
    parameter COEF_STRUCTURE = "Asymmetric",
    parameter DECIMATOR_RATE = 2           ,
    parameter INTERPOLATOR_RATE = 2           

) 
( 
    i_clk              ,
    i_rstn             ,
    
    i_axi4s_data_tvalid,
    i_axi4s_data_tdata ,
    i_axi4s_data_tlast ,
    
    o_chk_over         ,
    o_chk_err
);

input                   i_clk              ;
input                   i_rstn             ;
input                   i_axi4s_data_tvalid;
input [DATA_WIDTH-1:0]  i_axi4s_data_tdata ;
input                   i_axi4s_data_tlast ;
output reg              o_chk_over         ;
output                  o_chk_err              ;


function integer clog2;
    input integer n;
    begin
        n = n - 1;
        for (clog2=0; n>0; clog2=clog2+1)
            n = n >> 1;
    end
endfunction

localparam DATA_SAMPLES = (FILTER_TYPE == "Decimator") ? (1024 % DECIMATOR_RATE == 0 ? 1024 / DECIMATOR_RATE : 1024 / DECIMATOR_RATE + 1) : 1024;
localparam DATA_CNT_WIDTH = clog2(DATA_SAMPLES)+1;

reg [DATA_CNT_WIDTH-1:0] data_cnt;
reg [DATA_CNT_WIDTH-1:0] wait_cnt;
reg data_cnt_err;

always @(posedge i_clk or negedge i_rstn)
begin
    if(~i_rstn)
        data_cnt <= {DATA_CNT_WIDTH{1'b0}};
    else if(i_axi4s_data_tvalid)
        data_cnt <= data_cnt + 1'b1;
end

always @(posedge i_clk or negedge i_rstn) 
begin
    if(~i_rstn)
        data_cnt_err <= 1'b0;
    else if(o_chk_over == 1'b1 && data_cnt != DATA_SAMPLES)
        data_cnt_err <= 1'b1;
end 

always @(posedge i_clk or negedge i_rstn) 
begin
    if(~i_rstn)
        wait_cnt <= {DATA_CNT_WIDTH{1'b0}};     
    else if(i_axi4s_data_tvalid)
        wait_cnt <= {DATA_CNT_WIDTH{1'b0}}; 
    else if(~i_axi4s_data_tvalid)
        wait_cnt <= wait_cnt + 1'b1;
end

always @(posedge i_clk or negedge i_rstn) 
begin
    if(~i_rstn)
        o_chk_over <= 1'b0;     
    else if(wait_cnt == DATA_SAMPLES-1)
        o_chk_over <= 1'b1;
end

assign o_chk_err = data_cnt_err; 
       
endmodule      
