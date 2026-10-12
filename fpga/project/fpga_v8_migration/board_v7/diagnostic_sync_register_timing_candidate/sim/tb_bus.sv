`timescale 1ns/1ps
module sdb_legacy_slave #(parameter TAG=0)(
 input clk,rst,awvalid,output awready,input [31:0] awaddr,
 input wvalid,output wready,input [31:0] wdata,input [3:0] wstrb,
 output reg bvalid,input bready,output [1:0] bresp,
 input arvalid,output arready,input [31:0] araddr,
 output reg rvalid,input rready,output reg [31:0] rdata,output [1:0] rresp
);
 reg have; reg [31:0] addr;reg [3:0] pace=0;
 integer writes=0,reads=0;
 always @(posedge clk) pace<=pace+1;
 assign awready=!have && !bvalid && pace[1:0]==0; assign wready=have && !bvalid && pace[1:0]==3;
 assign arready=!rvalid && pace[2:0]==5; assign bresp=0; assign rresp=0;
 always @(posedge clk) if(rst) begin have<=0;bvalid<=0;rvalid<=0;rdata<=0;addr<=0; end
 else begin
  if(awvalid && awready) begin have<=1;addr<=awaddr;end
  if(wvalid && wready) begin
   have<=0;bvalid<=1;writes<=writes+1;
   if(wdata!==32'h12345678 || wstrb!==4'hf) $fatal(1,"FAIL legacy write payload");
  end
  if(bvalid && bready) bvalid<=0;
  if(arvalid && arready) begin rvalid<=1;rdata<=araddr ^ (32'ha0000000+TAG);reads<=reads+1;end
  if(rvalid && rready) rvalid<=0;
 end
endmodule

module tb_v7_sdb;
 reg clk=0,camclk=0,rst=1;
 always #5 clk=~clk;
 always #7 camclk=~camclk;
 reg [3:0] cr=15,rawvs=0,href=0,capvs=0,capvalid=0;
 reg u_awvalid=0,u_wvalid=0,u_bready=0,u_arvalid=0,u_rready=0;
 reg [31:0] u_awaddr=0,u_araddr=0;
 reg [127:0] dma_wdata=0;reg [15:0] dma_wstrb=15;
 wire u_awready,u_wready,u_bvalid,u_arready,u_rvalid;
 wire [1:0] u_bresp,u_rresp;wire [127:0] dma_rdata;
 `include "fixture.vh"
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
   else if(order==1) begin w(v,strb);repeat(3) @(negedge clk);aw(a);end
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
  begin ar(a);take_r(v,expected);end
 endtask
 task marker;
  begin @(negedge camclk);rawvs=15;repeat(4) @(negedge camclk);rawvs=0;repeat(6) @(negedge camclk);end
 endtask
 task frame;
  begin @(negedge camclk);href=15;repeat(16) @(negedge camclk);href=0;repeat(8) @(negedge camclk);marker();end
 endtask
 task publish;
  begin repeat(11) marker();frame();repeat(20) @(negedge clk);end
 endtask
 task reset_cam(input [3:0] mask);
  begin #2;cr=mask;#2;cr=0;repeat(12) @(negedge clk);end
 endtask
 integer c,j;reg [31:0] base;
 initial begin
  #100;@(negedge clk);rst=0;cr=0;repeat(12) @(negedge clk);
  read_reg('h20001030,d,2); // no lease
  write_reg('h20001010,1,0,2); // no snapshot
  publish();
  for(c=0;c<4;c++) begin
   base='h20001000+c*256;
   read_reg(base,d);check(d[2],"available four cameras");
   write_reg(base+'h10,1,c%3);
   read_reg(base,d);check(d[0],"ACQUIRE");
   for(j=0;j<16;j++) begin
    write_reg(base+'h20,j,j%3);read_reg(base+'h30,d);
    if(j==15) check(d=='h53464401,"format all cameras");
    if(j==1) check(d==16,"accepted bytes real capture");
    if(j==4 || j==5) check(d==8,"valid count real capture");
   end
  end
  $display("PASS four cameras ACQUIRE all16 fields AW/W three orders");
  // Repeated acquire does not replace a held bank while more frames arrive.
  write_reg('h20001320,0);read_reg('h20001330,e0);frame();frame();
  write_reg('h20001310,1);read_reg('h20001330,e1);check(e0==e1,"repeat acquire preserves bank");
  // Independent read can finish while B is stalled; camera reset cannot erase B.
  fork aw('h20001320);w(15);join
  wait(u_bvalid);reset_cam(8);read_reg('h20001340,d);
  check(u_bvalid && !u_awready && !u_wready,"stalled B retains transaction ownership");b(0);
  $display("PASS repeated ACQUIRE and concurrent read stalled B camera reset");
  read_reg('h20001040,e0);
  write_reg('h20001020,15);
  ar('h20001030);wait(u_rvalid);#1;held=dma_rdata[31:0];check(held=='h53464401,"old response");
  reset_cam(1);
  check(u_rvalid && dma_rdata[31:0]==held && u_rresp==0,"stalled response survives cam reset");
  take_r(d);read_reg('h20001040,e1);check(e1!=e0,"epoch detects reset");
  read_reg('h20001030,d,2);read_reg('h20001130,d); // other camera survives
  $display("PASS stalled R camera reset epoch and camera isolation");
  // Accepted AR must terminate even if reset erases the local read pulse.
  ar('h20001130);reset_cam(2);take_r(d,2);
  $display("PASS accepted AR camera reset completes SLVERR");
  // Multi-field host algorithm detects a reset between otherwise successful reads.
  read_reg('h20001240,e0);write_reg('h20001220,0);read_reg('h20001230,d);
  reset_cam(4);read_reg('h20001230,d,2);publish();
  write_reg('h20001210,1);write_reg('h20001220,15);read_reg('h20001230,d);
  read_reg('h20001240,e1);check(e0!=e1,"multi field reset epoch mismatch");
  write_reg('h20001210,2);read_reg('h20001230,d,2);
  $display("PASS multi-field reset reacquire RELEASE no lease");
  // Every non-register byte offset in the exact aperture must error, not alias.
  for(c=0;c<4;c++) for(j=0;j<256;j++) begin
   if(j!='h00 && j!='h20 && j!='h30 && j!='h40)
    read_reg('h20001000+c*256+j,d,2);
  end
  write_reg('h20001314,1,1,2);write_reg('h20001320,16,2,2);
  write_reg('h20001310,3,0,2);write_reg('h20001310,1,0,2,1);
  $display("PASS exact byte-offset alias rejection and illegal commands strobes");
  // Frozen pcie_fifo lines 358/668 implement this BEFORE the real bridge.
  // This is a model of the address expression, not a simulation of PCIe IP.
  for(j=0;j<16;j++) begin
   base=(('h20001000+j)>>4)<<4;
   check(base=='h20001000,"DMA rounds low4: driver must reject unaligned");
  end
  read_reg(('h20001004>>4)<<4,d);check(u_rresp==0,"DMA aligned alias reaches STATUS");
  $display("PASS DMA alignment expression demonstrates upstream alias; raw AXIL rejects low offsets");
  // Existing decoder behavior, including the special CDC read slots.
  read_reg('h20000000,d);check(d==('h20000000 ^ 'ha0000000),"CAM1");
  read_reg('h20000100,d);check(d==('h20000100 ^ 'ha0000001),"PREP");
  read_reg('h20000200,d);check(d==('h20000200 ^ 'ha0000002),"CAM2");
  read_reg('h20000400,d);check(d==('h20000400 ^ 'ha0000003),"CAM3");
  read_reg('h20000600,d);check(d==('h20000600 ^ 'ha0000004),"CAM4");
  read_reg('h20000800,d);check(d==('h20000800 ^ 'ha0000001),"motion");
  for(c=0;c<4;c++) begin
   base='h20000190+c*512;
   read_reg(base,d);check(d==(base ^ ('ha0000000+(c==0?0:c+1))),"CDC special read");
   write_reg('h20000000+c*512,'h12345678,c%3);
  end
  write_reg('h20000100,'h12345678,1);write_reg('h20000800,'h12345678,2);
  // Outside aperture stays transparent, including historical aliases.
  read_reg('h30001030,d);check(d==('h30001030 ^ 'ha0000000),"high address not intercepted");
  read_reg('h20001400,d);check(d==('h20001400 ^ 'ha0000003),"upper boundary transparent");
  check(slave0.writes==1 && slave1.writes==2 && slave2.writes==1 && slave3.writes==1 && slave4.writes==1,"legacy write destinations");
  $display("PASS frozen bridge decoder old CAM PREP motion CDC routes transparent");
  // Interface reset is the only reset permitted to discard a response.
  ar('h20001040);wait(u_rvalid);@(negedge clk);rst=1;
  repeat(3) @(negedge clk);check(!u_rvalid && !u_bvalid,"AXI reset clears transactions");rst=0;
  repeat(12) @(negedge clk);read_reg('h20001030,d,2);
  $display("DSR_BUS_COMPARE_PASS cycles=%0d",bus_cycles);$display("SDB_ALL_PASS checks=%0d",checks);$finish;
 end
 initial begin #3000000;$fatal(1,"FAIL watchdog");end
 reg stalled_r=0,stalled_b=0;reg [127:0] last_data;reg [1:0] last_rresp,last_bresp;
 always @(posedge clk) begin
  if(!rst) begin
   if(stalled_r) check(u_rvalid && dma_rdata===last_data && u_rresp===last_rresp,"global AXI R stability");
   if(stalled_b) check(u_bvalid && u_bresp===last_bresp,"global AXI B stability");
  end
  stalled_r<=!rst && u_rvalid && !u_rready;stalled_b<=!rst && u_bvalid && !u_bready;
  last_data<=dma_rdata;last_rresp<=u_rresp;last_bresp<=u_bresp;
 end
endmodule
