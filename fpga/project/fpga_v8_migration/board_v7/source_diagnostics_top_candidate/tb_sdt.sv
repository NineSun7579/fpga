`timescale 1ns/1ps
module tb_sdt;
reg clk=0,camclk=0,rst=1,ctrlclk=0; always #5 clk=~clk; always #7 camclk=~camclk; always #20 ctrlclk=~ctrlclk;
reg [3:0] rawvs=0,href=0,camrun=0;
reg u_awvalid=0,u_wvalid=0,u_bready=0,u_arvalid=0,u_rready=0;
 reg [31:0] u_awaddr=0,u_araddr=0;
 reg [127:0] dma_wdata=0;reg [15:0] dma_wstrb=15;
 wire u_awready,u_wready,u_bvalid,u_arready,u_rvalid;
 wire [1:0] u_bresp,u_rresp;wire [127:0] dma_rdata;
 
GTP_GRS GRS_INST (.GRS_N(1'b1));
v7_sdt_top dut(.free_clk(1'b0),.button_rst_n(1'b1),.perst_n(1'b0),.ref_clk_p(1'b0),.ref_clk_n(1'b1),.rxn(2'b0),.rxp(2'b0),.sfp_l2rxn(1'b0),.sfp_l2rxp(1'b0),.cmos1_pclk(camclk),.cmos1_vsync(rawvs[0]),.cmos1_href(href[0]),.cmos1_data(8'h55),.cmos2_pclk(camclk),.cmos2_vsync(rawvs[1]),.cmos2_href(href[1]),.cmos2_data(8'h55),.cmos3_pclk(camclk),.cmos3_vsync(rawvs[2]),.cmos3_href(href[2]),.cmos3_data(8'h55),.cmos4_pclk(camclk),.cmos4_vsync(rawvs[3]),.cmos4_href(href[3]),.cmos4_data(8'h55));
initial begin force dut.axi_clk=clk; force dut.ddr_init_done=!rst; force dut.clk_50m=ctrlclk;
force dut.pcie_axi_awvalid=u_awvalid;
force dut.pcie_axi_awaddr=u_awaddr;
force dut.pcie_axi_wvalid=u_wvalid;
force dut.pcie_axi_bready=u_bready;
force dut.pcie_axi_arvalid=u_arvalid;
force dut.pcie_axi_araddr=u_araddr;
force dut.pcie_axi_rready=u_rready;
force dut.pcie_axi_wdata=dma_wdata;
force dut.pcie_axi_wstrb=dma_wstrb;
force dut.pcie_axi_wlast=1'b1;
force dut.pcie_axi_awid=0;
force dut.pcie_axi_awlen=0;
force dut.pcie_axi_awsize=4;
force dut.pcie_axi_awburst=1;
force dut.pcie_axi_awlock=0;
force dut.pcie_axi_awcache=0;
force dut.pcie_axi_awprot=0;
force dut.pcie_axi_awqos=0;
force dut.pcie_axi_arid=0;
force dut.pcie_axi_arlen=0;
force dut.pcie_axi_arsize=4;
force dut.pcie_axi_arburst=1;
force dut.pcie_axi_arlock=0;
force dut.pcie_axi_arcache=0;
force dut.pcie_axi_arprot=0;
force dut.pcie_axi_arqos=0;
force dut.ov5640_top.ov5640.cam_init_done=camrun[0];
force dut.ov5640_top.ov5640.i2c_start_en=camrun[0];
force dut.cam2_ov5640_top.ov5640.cam_init_done=camrun[1];
force dut.cam2_ov5640_top.ov5640.i2c_start_en=camrun[1];
force dut.cam3_ov5640_top.ov5640.cam_init_done=camrun[2];
force dut.cam3_ov5640_top.ov5640.i2c_start_en=camrun[2];
force dut.cam4_ov5640_top.ov5640.cam_init_done=camrun[3];
force dut.cam4_ov5640_top.ov5640.i2c_start_en=camrun[3];
end
assign u_awready=dut.pcie_axi_awready;
assign u_wready=dut.pcie_axi_wready;
assign u_bvalid=dut.pcie_axi_bvalid;
assign u_bresp=dut.pcie_axi_bresp;
assign u_arready=dut.pcie_axi_arready;
assign u_rvalid=dut.pcie_axi_rvalid;
assign u_rresp=dut.pcie_axi_rresp;
assign dma_rdata=dut.pcie_axi_rdata;
integer checks=0; reg [31:0] d,e0,e1,held;reg [1:0] resp;
 task check(input bit ok,input string msg);
  begin checks++;if(!ok) $fatal(1,"FAIL %s t=%0t",msg,$time);end
 endtask
 task aw(input [31:0] a);
  begin @(negedge clk);u_awaddr=a;u_awvalid=1;
   do @(posedge clk); while(!u_awready);
   @(negedge clk);u_awvalid=0;u_awaddr=32'hdeadbeef;
  end
 endtask
 task w(input [31:0] v,input [3:0] strb=15);
  begin @(negedge clk);dma_wdata={96'hbadbadbad,v};dma_wstrb={12'hfff,strb};u_wvalid=1;
   do @(posedge clk); while(!u_wready);
   @(negedge clk);u_wvalid=0;dma_wdata=0;
  end
 endtask
 task b(input [1:0] expected);
  reg [1:0] h;
  begin wait(u_bvalid);#1;h=u_bresp;check(h==expected,"BRESP");
   repeat(4) begin @(posedge clk);#1;check(u_bvalid && u_bresp==h,"B hold");end
   @(negedge clk);u_bready=1;@(negedge clk);u_bready=0;
  end
 endtask
 task write_reg(input [31:0] a,input [31:0] v,input integer order=0,input [1:0] expected=0,input [3:0] strb=15);
  begin
   if(order==0) begin aw(a);repeat(3) @(negedge clk);w(v,strb);end
   else if(order==1) fork w(v,strb);begin repeat(3) @(negedge clk);aw(a);end join
   else fork aw(a);w(v,strb);join
   b(expected);
  end
 endtask
 task ar(input [31:0] a);
  begin @(negedge clk);u_arvalid=1;u_araddr=a;
   do @(posedge clk);while(!u_arready);
   @(negedge clk);u_arvalid=0;u_araddr=32'hcafef00d;
  end
 endtask
 task take_r(output [31:0] v,input [1:0] expected=0);
  reg [127:0] h;reg [1:0] hr;
  begin wait(u_rvalid);#1;h=dma_rdata;hr=u_rresp;v=h[31:0];
   check(hr==expected,"RRESP");check(h[127:32]==0,"bridge zero high96");
   repeat(4) begin @(posedge clk);#1;check(u_rvalid && dma_rdata===h && u_rresp===hr,"R hold");end
   @(negedge clk);u_rready=1;@(negedge clk);u_rready=0;
  end
 endtask
 task read_reg(input [31:0] a,output [31:0] v,input [1:0] expected=0);
  begin $display("READ addr=%h expected=%h",a,expected); ar(a);take_r(v,expected);end
 endtask
 
reg stalled_r=0,stalled_b=0;reg [127:0] last_data;reg [1:0] last_rresp,last_bresp;
 always @(posedge clk) begin
  if(!rst) begin
   if(stalled_r) check(u_rvalid && dma_rdata===last_data && u_rresp===last_rresp,"global AXI R stability");
   if(stalled_b) check(u_bvalid && u_bresp===last_bresp,"global AXI B stability");
  end
  stalled_r<=!rst && u_rvalid && !u_rready;stalled_b<=!rst && u_bvalid && !u_bready;
  last_data<=dma_rdata;last_rresp<=u_rresp;last_bresp<=u_bresp;
 end

`include "scenario.vh"
endmodule