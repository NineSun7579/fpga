// TC01: factor the default camera routes directly from their page bits.
// The exact motion page cannot be CAM2/3/4. Remove its wide comparator from
// those live write routes. No registers added to requests or responses.
module ovreg_axil_decode_tc01 #(parameter ADDR_SEL_LSB=8)(
    input clk, rst,
    input s_awvalid, output s_awready, input [31:0] s_awaddr,
    input s_wvalid, output s_wready, input [31:0] s_wdata, input [3:0] s_wstrb,
    output s_bvalid, input s_bready, output [1:0] s_bresp,
    input s_arvalid, output s_arready, input [31:0] s_araddr,
    output s_rvalid, input s_rready, output [31:0] s_rdata, output [1:0] s_rresp,
    output m0_awvalid, input m0_awready, output [31:0] m0_awaddr,
    output m0_wvalid, input m0_wready, output [31:0] m0_wdata, output [3:0] m0_wstrb,
    input m0_bvalid, output m0_bready, input [1:0] m0_bresp,
    output m0_arvalid, input m0_arready, output [31:0] m0_araddr,
    input m0_rvalid, output m0_rready, input [31:0] m0_rdata, input [1:0] m0_rresp,
    output m1_awvalid, input m1_awready, output [31:0] m1_awaddr,
    output m1_wvalid, input m1_wready, output [31:0] m1_wdata, output [3:0] m1_wstrb,
    input m1_bvalid, output m1_bready, input [1:0] m1_bresp,
    output m1_arvalid, input m1_arready, output [31:0] m1_araddr,
    input m1_rvalid, output m1_rready, input [31:0] m1_rdata, input [1:0] m1_rresp,
    output m2_awvalid, input m2_awready, output [31:0] m2_awaddr,
    output m2_wvalid, input m2_wready, output [31:0] m2_wdata, output [3:0] m2_wstrb,
    input m2_bvalid, output m2_bready, input [1:0] m2_bresp,
    output m2_arvalid, input m2_arready, output [31:0] m2_araddr,
    input m2_rvalid, output m2_rready, input [31:0] m2_rdata, input [1:0] m2_rresp,
    output m3_awvalid, input m3_awready, output [31:0] m3_awaddr,
    output m3_wvalid, input m3_wready, output [31:0] m3_wdata, output [3:0] m3_wstrb,
    input m3_bvalid, output m3_bready, input [1:0] m3_bresp,
    output m3_arvalid, input m3_arready, output [31:0] m3_araddr,
    input m3_rvalid, output m3_rready, input [31:0] m3_rdata, input [1:0] m3_rresp,
    output m4_awvalid, input m4_awready, output [31:0] m4_awaddr,
    output m4_wvalid, input m4_wready, output [31:0] m4_wdata, output [3:0] m4_wstrb,
    input m4_bvalid, output m4_bready, input [1:0] m4_bresp,
    output m4_arvalid, input m4_arready, output [31:0] m4_araddr,
    input m4_rvalid, output m4_rready, input [31:0] m4_rdata, input [1:0] m4_rresp
);
    function [4:0] route_mask(input [3:0] code);
        begin
            route_mask[4]=(code[3:2]==2'b01) && code[1];
            route_mask[3]=(code[3:2]==2'b01) && !code[1];
            route_mask[0]=(code[3:2]!=2'b01) && (code[1:0]==2'b00);
            route_mask[2]=(code[3:2]!=2'b01) && (code[1:0]==2'b10);
            route_mask[1]=!(route_mask[4] || route_mask[3] || route_mask[0] || route_mask[2]);
        end
    endfunction
    wire motion_aw=(s_awaddr[31:8]==24'h200008);
    wire motion_ar=(s_araddr[31:8]==24'h200008);
    wire [4:0] aw_live;
    generate if (ADDR_SEL_LSB==8) begin : default_route
        wire page34=(s_awaddr[11:10]==2'b01);
        assign aw_live[4]=page34 && s_awaddr[9];
        assign aw_live[3]=page34 && !s_awaddr[9];
        assign aw_live[2]=!page34 && (s_awaddr[9:8]==2'b10);
        assign aw_live[0]=!page34 && (s_awaddr[9:8]==2'b00) && !motion_aw;
        assign aw_live[1]=!(aw_live[4] || aw_live[3] || aw_live[2] || aw_live[0]);
    end else begin : parameter_route
        assign aw_live=route_mask(motion_aw?4'h1:s_awaddr[ADDR_SEL_LSB+3:ADDR_SEL_LSB]);
    end endgenerate
    reg [4:0] aw_saved;
    always @(posedge clk) begin
        if (rst) aw_saved<=5'b00001;
        else if (s_awvalid && s_awready) aw_saved<=aw_live;
    end
    wire [4:0] aw=s_awvalid?aw_live:aw_saved;
    wire cdc_read=(s_araddr[31:11]==(32'h20000000>>11)) &&
                  (s_araddr[11:9]<4) &&
                  ((s_araddr[8:0]==9'h190) || (s_araddr[8:0]==9'h1a0) ||
                   (s_araddr[8:0]==9'h1b0) || (s_araddr[8:0]==9'h1c0));
    wire [3:0] ar_route=motion_ar?4'h1:cdc_read?{s_araddr[11:9],1'b0}:
                         s_araddr[ADDR_SEL_LSB+3:ADDR_SEL_LSB];
    reg [3:0] ar_sel;
    always @(posedge clk) begin
        if (rst) ar_sel<=0;
        else if (s_arvalid && s_arready) ar_sel<=ar_route;
    end
    wire [4:0] ar=route_mask(s_arvalid?ar_route:ar_sel);
    wire [4:0] br=aw_saved;
    wire [4:0] rr=route_mask(ar_sel);
    assign m0_awvalid=s_awvalid && aw[0];
    assign m1_awvalid=s_awvalid && aw[1];
    assign m2_awvalid=s_awvalid && aw[2];
    assign m3_awvalid=s_awvalid && aw[3];
    assign m4_awvalid=s_awvalid && aw[4];
    assign s_awready=aw[4]?m4_awready:aw[3]?m3_awready:aw[0]?m0_awready:aw[2]?m2_awready:m1_awready;
    assign m0_awaddr=s_awaddr; assign m1_awaddr=s_awaddr; assign m2_awaddr=s_awaddr;
    assign m3_awaddr=s_awaddr; assign m4_awaddr=s_awaddr;
    assign m0_wvalid=s_wvalid && aw[0]; assign m1_wvalid=s_wvalid && aw[1];
    assign m2_wvalid=s_wvalid && aw[2]; assign m3_wvalid=s_wvalid && aw[3];
    assign m4_wvalid=s_wvalid && aw[4];
    assign s_wready=aw[4]?m4_wready:aw[3]?m3_wready:aw[0]?m0_wready:aw[2]?m2_wready:m1_wready;
    assign m0_wdata=s_wdata; assign m1_wdata=s_wdata; assign m2_wdata=s_wdata;
    assign m3_wdata=s_wdata; assign m4_wdata=s_wdata;
    assign m0_wstrb=s_wstrb; assign m1_wstrb=s_wstrb; assign m2_wstrb=s_wstrb;
    assign m3_wstrb=s_wstrb; assign m4_wstrb=s_wstrb;
    assign m0_bready=s_bready && br[0]; assign m1_bready=s_bready && br[1];
    assign m2_bready=s_bready && br[2]; assign m3_bready=s_bready && br[3];
    assign m4_bready=s_bready && br[4];
    assign s_bvalid=br[4]?m4_bvalid:br[3]?m3_bvalid:br[0]?m0_bvalid:br[2]?m2_bvalid:m1_bvalid;
    assign s_bresp=br[4]?m4_bresp:br[3]?m3_bresp:br[0]?m0_bresp:br[2]?m2_bresp:m1_bresp;
    assign m0_arvalid=s_arvalid && ar[0]; assign m1_arvalid=s_arvalid && ar[1];
    assign m2_arvalid=s_arvalid && ar[2]; assign m3_arvalid=s_arvalid && ar[3];
    assign m4_arvalid=s_arvalid && ar[4];
    assign s_arready=ar[4]?m4_arready:ar[3]?m3_arready:ar[0]?m0_arready:ar[2]?m2_arready:m1_arready;
    assign m0_araddr=s_araddr; assign m1_araddr=s_araddr; assign m2_araddr=s_araddr;
    assign m3_araddr=s_araddr; assign m4_araddr=s_araddr;
    assign m0_rready=s_rready && rr[0]; assign m1_rready=s_rready && rr[1];
    assign m2_rready=s_rready && rr[2]; assign m3_rready=s_rready && rr[3];
    assign m4_rready=s_rready && rr[4];
    assign s_rvalid=rr[4]?m4_rvalid:rr[3]?m3_rvalid:rr[0]?m0_rvalid:rr[2]?m2_rvalid:m1_rvalid;
    assign s_rdata=rr[4]?m4_rdata:rr[3]?m3_rdata:rr[0]?m0_rdata:rr[2]?m2_rdata:m1_rdata;
    assign s_rresp=rr[4]?m4_rresp:rr[3]?m3_rresp:rr[0]?m0_rresp:rr[2]?m2_rresp:m1_rresp;
endmodule
