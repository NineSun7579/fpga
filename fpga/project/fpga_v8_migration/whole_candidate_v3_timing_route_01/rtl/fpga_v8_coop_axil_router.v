`timescale 1ns/1ps
// Isolated Verilog-2001 two-child router; addresses stay full and untranslated.
// 0x000..0x0ff -> m0 cooperative; all other addresses -> m1 exact capture decode.
module fpga_v8_coop_axil_router (
    input wire clk,input wire rst_n,
    input wire [31:0] s_axil_awaddr,input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,output wire s_axil_wready,
    output reg [1:0] s_axil_bresp,output wire s_axil_bvalid,input wire s_axil_bready,
    input wire [31:0] s_axil_araddr,input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,output wire s_axil_arready,
    output reg [31:0] s_axil_rdata,output reg [1:0] s_axil_rresp,
    output wire s_axil_rvalid,input wire s_axil_rready,
    output wire [31:0] m0_axil_awaddr,output wire [2:0] m0_axil_awprot,
    output wire m0_axil_awvalid,input wire m0_axil_awready,
    output wire [31:0] m0_axil_wdata,output wire [3:0] m0_axil_wstrb,
    output wire m0_axil_wvalid,input wire m0_axil_wready,
    input wire [1:0] m0_axil_bresp,input wire m0_axil_bvalid,output wire m0_axil_bready,
    output wire [31:0] m0_axil_araddr,output wire [2:0] m0_axil_arprot,
    output wire m0_axil_arvalid,input wire m0_axil_arready,
    input wire [31:0] m0_axil_rdata,input wire [1:0] m0_axil_rresp,
    input wire m0_axil_rvalid,output wire m0_axil_rready,
    output wire [31:0] m1_axil_awaddr,output wire [2:0] m1_axil_awprot,
    output wire m1_axil_awvalid,input wire m1_axil_awready,
    output wire [31:0] m1_axil_wdata,output wire [3:0] m1_axil_wstrb,
    output wire m1_axil_wvalid,input wire m1_axil_wready,
    input wire [1:0] m1_axil_bresp,input wire m1_axil_bvalid,output wire m1_axil_bready,
    output wire [31:0] m1_axil_araddr,output wire [2:0] m1_axil_arprot,
    output wire m1_axil_arvalid,input wire m1_axil_arready,
    input wire [31:0] m1_axil_rdata,input wire [1:0] m1_axil_rresp,
    input wire m1_axil_rvalid,output wire m1_axil_rready
);
    localparam [1:0] CAP=0,SEND=1,WAIT_RESP=2,FULL_RESP=3;
    reg [1:0] ws,rs;
    reg aw_held,w_held,wr_route,rd_route,aw_pending,w_pending;
    reg [31:0] aw_addr,w_data,ar_addr;
    reg [2:0] aw_prot,ar_prot;
    reg [3:0] w_strb;
    wire child_awready=wr_route ? m1_axil_awready : m0_axil_awready;
    wire child_wready=wr_route ? m1_axil_wready : m0_axil_wready;
    wire child_bvalid=wr_route ? m1_axil_bvalid : m0_axil_bvalid;
    wire [1:0] child_bresp=wr_route ? m1_axil_bresp : m0_axil_bresp;
    wire child_arready=rd_route ? m1_axil_arready : m0_axil_arready;
    wire child_rvalid=rd_route ? m1_axil_rvalid : m0_axil_rvalid;
    wire [1:0] child_rresp=rd_route ? m1_axil_rresp : m0_axil_rresp;
    wire [31:0] child_rdata=rd_route ? m1_axil_rdata : m0_axil_rdata;
    assign s_axil_awready=rst_n && ws==CAP && !aw_held;
    assign s_axil_wready=rst_n && ws==CAP && !w_held;
    assign s_axil_bvalid=rst_n && ws==FULL_RESP;
    assign s_axil_arready=rst_n && rs==CAP;
    assign s_axil_rvalid=rst_n && rs==FULL_RESP;
    assign m0_axil_awaddr=aw_addr;assign m1_axil_awaddr=aw_addr;
    assign m0_axil_awprot=aw_prot;assign m1_axil_awprot=aw_prot;
    assign m0_axil_wdata=w_data;assign m1_axil_wdata=w_data;
    assign m0_axil_wstrb=w_strb;assign m1_axil_wstrb=w_strb;
    assign m0_axil_araddr=ar_addr;assign m1_axil_araddr=ar_addr;
    assign m0_axil_arprot=ar_prot;assign m1_axil_arprot=ar_prot;
    assign m0_axil_awvalid=rst_n && ws==SEND && !wr_route && aw_pending;
    assign m1_axil_awvalid=rst_n && ws==SEND && wr_route && aw_pending;
    assign m0_axil_wvalid=rst_n && ws==SEND && !wr_route && w_pending;
    assign m1_axil_wvalid=rst_n && ws==SEND && wr_route && w_pending;
    assign m0_axil_bready=rst_n && ws==WAIT_RESP && !wr_route;
    assign m1_axil_bready=rst_n && ws==WAIT_RESP && wr_route;
    assign m0_axil_arvalid=rst_n && rs==SEND && !rd_route;
    assign m1_axil_arvalid=rst_n && rs==SEND && rd_route;
    assign m0_axil_rready=rst_n && rs==WAIT_RESP && !rd_route;
    assign m1_axil_rready=rst_n && rs==WAIT_RESP && rd_route;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            ws<=CAP;rs<=CAP;aw_held<=0;w_held<=0;wr_route<=0;rd_route<=0;
            aw_pending<=0;w_pending<=0;aw_addr<=0;w_data<=0;ar_addr<=0;
            aw_prot<=0;ar_prot<=0;w_strb<=0;
            s_axil_bresp<=0;s_axil_rdata<=0;s_axil_rresp<=0;
        end else begin
            if(s_axil_awvalid && s_axil_awready) begin
                aw_held<=1;aw_addr<=s_axil_awaddr;aw_prot<=s_axil_awprot;
                wr_route<=s_axil_awaddr>=32'h100;
            end
            if(s_axil_wvalid && s_axil_wready) begin w_held<=1;w_data<=s_axil_wdata;w_strb<=s_axil_wstrb;end
            if(ws==CAP && aw_held && w_held) begin ws<=SEND;aw_pending<=1;w_pending<=1;end
            if(ws==SEND) begin
                if(aw_pending && child_awready) aw_pending<=0;
                if(w_pending && child_wready) w_pending<=0;
                if((!aw_pending || child_awready) && (!w_pending || child_wready)) ws<=WAIT_RESP;
            end
            if(ws==WAIT_RESP && child_bvalid) begin s_axil_bresp<=child_bresp;ws<=FULL_RESP;end
            if(s_axil_bvalid && s_axil_bready) begin ws<=CAP;aw_held<=0;w_held<=0;end
            if(s_axil_arvalid && s_axil_arready) begin
                ar_addr<=s_axil_araddr;ar_prot<=s_axil_arprot;
                rd_route<=s_axil_araddr>=32'h100;rs<=SEND;
            end
            if(rs==SEND && child_arready) rs<=WAIT_RESP;
            if(rs==WAIT_RESP && child_rvalid) begin
                s_axil_rdata<=child_rdata;s_axil_rresp<=child_rresp;rs<=FULL_RESP;
            end
            if(s_axil_rvalid && s_axil_rready) rs<=CAP;
        end
    end
endmodule
