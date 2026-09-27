`timescale 1ns/1ps
module tb_cam3_decode;
reg clk=0, rst=1;
always #5 clk=~clk;
reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
reg [31:0] awaddr=0,wdata=0,araddr=0;
reg [3:0] wstrb=15;
wire awready,wready,bvalid,arready,rvalid;
wire [1:0] bresp,rresp;
wire [31:0] rdata;
wire m_awvalid [0:3];
wire m_awready [0:3];
wire [31:0] m_awaddr [0:3];
wire m_wvalid [0:3];
wire m_wready [0:3];
wire [31:0] m_wdata [0:3];
wire [3:0] m_wstrb [0:3];
wire m_bvalid [0:3];
wire m_bready [0:3];
wire [1:0] m_bresp [0:3];
wire m_arvalid [0:3];
wire m_arready [0:3];
wire [31:0] m_araddr [0:3];
wire m_rvalid [0:3];
wire m_rready [0:3];
wire [31:0] m_rdata [0:3];
wire [1:0] m_rresp [0:3];
ovreg_axil_decode dut(.clk(clk),
.rst(rst),
.s_awvalid(awvalid),
.s_awready(awready),
.s_awaddr(awaddr),
.s_wvalid(wvalid),
.s_wready(wready),
.s_wdata(wdata),
.s_wstrb(wstrb),
.s_bvalid(bvalid),
.s_bready(bready),
.s_bresp(bresp),
.s_arvalid(arvalid),
.s_arready(arready),
.s_araddr(araddr),
.s_rvalid(rvalid),
.s_rready(rready),
.s_rdata(rdata),
.s_rresp(rresp),
.m0_awvalid(m_awvalid[0]),
.m0_awready(m_awready[0]),
.m0_awaddr(m_awaddr[0]),
.m0_wvalid(m_wvalid[0]),
.m0_wready(m_wready[0]),
.m0_wdata(m_wdata[0]),
.m0_wstrb(m_wstrb[0]),
.m0_bvalid(m_bvalid[0]),
.m0_bready(m_bready[0]),
.m0_bresp(m_bresp[0]),
.m0_arvalid(m_arvalid[0]),
.m0_arready(m_arready[0]),
.m0_araddr(m_araddr[0]),
.m0_rvalid(m_rvalid[0]),
.m0_rready(m_rready[0]),
.m0_rdata(m_rdata[0]),
.m0_rresp(m_rresp[0]),
.m1_awvalid(m_awvalid[1]),
.m1_awready(m_awready[1]),
.m1_awaddr(m_awaddr[1]),
.m1_wvalid(m_wvalid[1]),
.m1_wready(m_wready[1]),
.m1_wdata(m_wdata[1]),
.m1_wstrb(m_wstrb[1]),
.m1_bvalid(m_bvalid[1]),
.m1_bready(m_bready[1]),
.m1_bresp(m_bresp[1]),
.m1_arvalid(m_arvalid[1]),
.m1_arready(m_arready[1]),
.m1_araddr(m_araddr[1]),
.m1_rvalid(m_rvalid[1]),
.m1_rready(m_rready[1]),
.m1_rdata(m_rdata[1]),
.m1_rresp(m_rresp[1]),
.m2_awvalid(m_awvalid[2]),
.m2_awready(m_awready[2]),
.m2_awaddr(m_awaddr[2]),
.m2_wvalid(m_wvalid[2]),
.m2_wready(m_wready[2]),
.m2_wdata(m_wdata[2]),
.m2_wstrb(m_wstrb[2]),
.m2_bvalid(m_bvalid[2]),
.m2_bready(m_bready[2]),
.m2_bresp(m_bresp[2]),
.m2_arvalid(m_arvalid[2]),
.m2_arready(m_arready[2]),
.m2_araddr(m_araddr[2]),
.m2_rvalid(m_rvalid[2]),
.m2_rready(m_rready[2]),
.m2_rdata(m_rdata[2]),
.m2_rresp(m_rresp[2]),
.m3_awvalid(m_awvalid[3]),
.m3_awready(m_awready[3]),
.m3_awaddr(m_awaddr[3]),
.m3_wvalid(m_wvalid[3]),
.m3_wready(m_wready[3]),
.m3_wdata(m_wdata[3]),
.m3_wstrb(m_wstrb[3]),
.m3_bvalid(m_bvalid[3]),
.m3_bready(m_bready[3]),
.m3_bresp(m_bresp[3]),
.m3_arvalid(m_arvalid[3]),
.m3_arready(m_arready[3]),
.m3_araddr(m_araddr[3]),
.m3_rvalid(m_rvalid[3]),
.m3_rready(m_rready[3]),
.m3_rdata(m_rdata[3]),
.m3_rresp(m_rresp[3]));
ov5640_reg #(.BASE_ADDR(32'h20000000)) slave0(.clk(clk),
.rst(rst),
.s_axi_awvalid(m_awvalid[0]),
.s_axi_awready(m_awready[0]),
.s_axi_awaddr(m_awaddr[0]),
.s_axi_wvalid(m_wvalid[0]),
.s_axi_wready(m_wready[0]),
.s_axi_wdata(m_wdata[0]),
.s_axi_wstrb(m_wstrb[0]),
.s_axi_bvalid(m_bvalid[0]),
.s_axi_bready(m_bready[0]),
.s_axi_bresp(m_bresp[0]),
.s_axi_arvalid(m_arvalid[0]),
.s_axi_arready(m_arready[0]),
.s_axi_araddr(m_araddr[0]),
.s_axi_rvalid(m_rvalid[0]),
.s_axi_rready(m_rready[0]),
.s_axi_rdata(m_rdata[0]),
.s_axi_rresp(m_rresp[0]));
ov5640_reg #(.BASE_ADDR(32'h20000100)) slave1(.clk(clk),
.rst(rst),
.s_axi_awvalid(m_awvalid[1]),
.s_axi_awready(m_awready[1]),
.s_axi_awaddr(m_awaddr[1]),
.s_axi_wvalid(m_wvalid[1]),
.s_axi_wready(m_wready[1]),
.s_axi_wdata(m_wdata[1]),
.s_axi_wstrb(m_wstrb[1]),
.s_axi_bvalid(m_bvalid[1]),
.s_axi_bready(m_bready[1]),
.s_axi_bresp(m_bresp[1]),
.s_axi_arvalid(m_arvalid[1]),
.s_axi_arready(m_arready[1]),
.s_axi_araddr(m_araddr[1]),
.s_axi_rvalid(m_rvalid[1]),
.s_axi_rready(m_rready[1]),
.s_axi_rdata(m_rdata[1]),
.s_axi_rresp(m_rresp[1]));
ov5640_reg #(.BASE_ADDR(32'h20000200)) slave2(.clk(clk),
.rst(rst),
.s_axi_awvalid(m_awvalid[2]),
.s_axi_awready(m_awready[2]),
.s_axi_awaddr(m_awaddr[2]),
.s_axi_wvalid(m_wvalid[2]),
.s_axi_wready(m_wready[2]),
.s_axi_wdata(m_wdata[2]),
.s_axi_wstrb(m_wstrb[2]),
.s_axi_bvalid(m_bvalid[2]),
.s_axi_bready(m_bready[2]),
.s_axi_bresp(m_bresp[2]),
.s_axi_arvalid(m_arvalid[2]),
.s_axi_arready(m_arready[2]),
.s_axi_araddr(m_araddr[2]),
.s_axi_rvalid(m_rvalid[2]),
.s_axi_rready(m_rready[2]),
.s_axi_rdata(m_rdata[2]),
.s_axi_rresp(m_rresp[2]));
ov5640_reg #(.BASE_ADDR(32'h20000400)) slave3(.clk(clk),
.rst(rst),
.s_axi_awvalid(m_awvalid[3]),
.s_axi_awready(m_awready[3]),
.s_axi_awaddr(m_awaddr[3]),
.s_axi_wvalid(m_wvalid[3]),
.s_axi_wready(m_wready[3]),
.s_axi_wdata(m_wdata[3]),
.s_axi_wstrb(m_wstrb[3]),
.s_axi_bvalid(m_bvalid[3]),
.s_axi_bready(m_bready[3]),
.s_axi_bresp(m_bresp[3]),
.s_axi_arvalid(m_arvalid[3]),
.s_axi_arready(m_arready[3]),
.s_axi_araddr(m_araddr[3]),
.s_axi_rvalid(m_rvalid[3]),
.s_axi_rready(m_rready[3]),
.s_axi_rdata(m_rdata[3]),
.s_axi_rresp(m_rresp[3]));

task wr(input [31:0] a, input [31:0] v);
begin
 @(negedge clk); awaddr=a; wdata=v; awvalid=1; wvalid=1;
 @(posedge clk); while (!(awready && wready)) @(posedge clk);
 @(negedge clk); awvalid=0; wvalid=0;
 wait(bvalid===1); repeat(3) @(negedge clk);
 if (!bvalid || bresp!==0) $fatal(1,"write response lost");
 bready=1; @(negedge clk); bready=0;
end endtask
task rd(input [31:0] a, input [31:0] expected);
begin
 @(negedge clk); araddr=a; arvalid=1;
 @(posedge clk); while(!arready) @(posedge clk);
 @(negedge clk); arvalid=0;
 wait(rvalid===1); repeat(3) @(negedge clk);
 if (!rvalid || rresp!==0 || rdata!==expected)
   $fatal(1,"READ addr=%h got=%h expected=%h",a,rdata,expected);
 rready=1; @(negedge clk); rready=0;
end endtask
initial begin
 repeat(5) @(negedge clk); rst=0;
 rd(32'h20000040,1); rd(32'h20000240,1); rd(32'h20000440,1);
 wr(32'h20000080,32'h00800000);
 wr(32'h20000280,32'h00c00000);
 wr(32'h20000480,32'h01000000);
 wr(32'h20000180,32'h00f00000);
 rd(32'h20000480,32'h01000000);
 rd(32'h20000280,32'h00c00000);
 rd(32'h20000080,32'h00800000);
 rd(32'h20000180,32'h00f00000);
 wr(32'h20000440,0); rd(32'h20000440,0);
 rd(32'h20000040,1); rd(32'h20000240,1);
 wr(32'h20000440,1); rd(32'h20000440,1);
 $display("CAM3_DECODE_PASS: four windows, isolated registers, stalled B/R");
 $finish;
end
initial begin #20000; $fatal(1,"TIMEOUT"); end
endmodule
