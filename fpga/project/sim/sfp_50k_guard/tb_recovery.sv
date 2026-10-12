`timescale 1ns/1ps
module tb_recovery;
 reg fc=0,vc=0,rst=0,ready=0;always #4 fc=~fc;always @(negedge fc)vc<=~vc;
 reg [18:0] video=0;wire [31:0] d;wire [3:0]k;
 sfp_video_tx tx(.vid_clk(vc),.vid_rst_n(rst),.vid_data(video),.fab_clk(fc),.fab_rst_n(rst),.link_ready(ready),.txd(d),.txk(k));
 wire vs,hs,de,ovf;wire [15:0]pix;
 sfp_video_rx rx(.i_clk(fc),.i_rst_n(rst),.i_en(rst),.i_rxd(d),.i_rxk(k),.o_vs(vs),.o_hs(hs),.o_de(de),.o_pix(pix),.o_overflow(ovf));
 integer n=0,sof=0,checks=0;reg prev_vs=0;reg block_edge;
 always @(posedge fc)begin
  if(rst && tx.u_fifo.full)$fatal(1,"TX FIFO full");
  block_edge=!tx.payload_go;
  #2;
  if(rst && block_edge && k==0)$fatal(1,"queued payload leaked after readiness loss");
  if(rst && tx.fifo_pop!==!tx.fifo_empty)$fatal(1,"FIFO drain changed");
 end
 always @(negedge fc)if(rst)begin
  if(ovf)$fatal(1,"RX overflow");
  if(vs && !prev_vs)begin sof=sof+1;n=0;end
  prev_vs=vs;
  if(de && sof==2)begin
   if(pix!==16'h2000+n)$fatal(1,"recovery identity n=%0d got=%h",n,pix);
   n=n+1;
  end
 end
 task symbol(input bit v,dd,input [15:0]p);
 begin @(negedge vc);video={v,1'b0,dd,p};end endtask
 integer i;
 initial begin
  #101;rst=1;repeat(32)symbol(0,0,0);ready=1;repeat(32)symbol(0,0,0);
  repeat(4)symbol(1,0,0);repeat(8)symbol(0,0,0);
  for(i=0;i<64;i=i+1)begin
   if(i==20)ready=0;if(i==40)ready=1;symbol(0,1,16'h1000+i);
  end
  repeat(64)symbol(0,0,0);
  repeat(4)symbol(1,0,0);repeat(8)symbol(0,0,0);
  for(i=0;i<64;i=i+1)symbol(0,1,16'h2000+i);
  repeat(128)symbol(0,0,0);
  if(sof!=2 || n!=64)$fatal(1,"recovery frame count sof=%0d pixels=%0d",sof,n);
  $display("PASS RECOVERY guard TX drains unchanged, flushes queued payload and recovers exact next frame");$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
