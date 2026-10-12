`timescale 1ns/1ps
// Ownership lasts through final B, including AW/W stalls; alternate contenders.
module background_write_arbiter (
    input wire clk, rst,
    input wire [63:0] in_awaddr,
    input wire [15:0] in_awlen,
    input wire [1:0] in_awvalid,
    output wire [1:0] in_awready,
    input wire [255:0] in_wdata,
    input wire [31:0] in_wstrb,
    input wire [1:0] in_wvalid, in_wlast,
    output wire [1:0] in_wready,
    output wire [3:0] in_bresp,
    output wire [1:0] in_bvalid,
    input wire [1:0] in_bready,
    output wire [31:0] awaddr,
    output wire [7:0] awlen,
    output wire awvalid,
    input wire awready,
    output wire [127:0] wdata,
    output wire [15:0] wstrb,
    output wire wvalid, wlast,
    input wire wready,
    input wire [1:0] bresp,
    input wire bvalid,
    output wire bready
);
    reg active, owner, preference;
    assign awaddr=in_awaddr[owner*32 +:32];
    assign awlen=in_awlen[owner*8 +:8];
    assign awvalid=active && in_awvalid[owner];
    assign wdata=in_wdata[owner*128 +:128];
    assign wstrb=in_wstrb[owner*16 +:16];
    assign wvalid=active && in_wvalid[owner];
    assign wlast=in_wlast[owner];
    assign bready=active && in_bready[owner];
    assign in_awready=active ? (owner ? {awready,1'b0} : {1'b0,awready}) : 0;
    assign in_wready=active ? (owner ? {wready,1'b0} : {1'b0,wready}) : 0;
    assign in_bvalid=active ? (owner ? {bvalid,1'b0} : {1'b0,bvalid}) : 0;
    assign in_bresp={bresp,bresp};
    always @(posedge clk) begin
        if(rst) begin active<=0; owner<=0; preference<=0; end
        else begin
            if(!active && |in_awvalid) begin
                active<=1;
                owner<=in_awvalid[preference] ? preference : !preference;
            end
            if(active && bvalid && bready) begin active<=0; preference<=!owner; end
        end
    end
endmodule
