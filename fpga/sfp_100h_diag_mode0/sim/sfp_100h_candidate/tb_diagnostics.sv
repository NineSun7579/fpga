`timescale 1ns/1ps
module tb_diagnostics;
 reg rx_clk=0,hclk=0,rst=0;always #4 rx_clk=~rx_clk;always #5.3 hclk=~hclk;
 reg en=0,vs=0,de=0,mal=0,ovf=0;reg [31:0]d=0;reg [3:0] k=9,disp=0,dec=0;reg [2:0] status=0;reg [1:0]phase=0;
 wire [511:0] snap;
 sfp_rx_diagnostics #(.NEW_PARSER(1)) dut(.rx_clk(rx_clk),.rx_rst_n(rst),.host_clk(hclk),.host_rst_n(rst),
 .link_en(en),.raw_d(d),.raw_k(k),.disp_err(disp),.decode_err(dec),.status(status),
 .phase(phase),.vs(vs),.de(de),.malformed(mal),.overflow(ovf),.host_snapshot(snap));
 integer i;
 task tick(input [3:0] ki,input [2:0]st,input vd,input dd,input [3:0]di,dc,input [1:0]ph);
 begin @(negedge rx_clk);k=ki;status=st;vs=vd;de=dd;disp=di;dec=dc;phase=ph;end endtask
 initial begin
  repeat(4)@(negedge rx_clk);rst=1;en=1;
  tick(9,0,1,0,0,0,0);tick(9,0,0,0,0,0,0);
  repeat(10)tick(0,2,0,1,1,2,0);
  tick(2,1,0,0,0,0,2);tick(4,1,0,0,0,0,2);
  tick(9,5,0,0,0,0,2);tick(9,0,1,0,0,0,2);
  tick(9,0,0,0,0,0,2);mal=1;
  repeat(64)@(negedge hclk);
  if(snap[1*32 +:32]!=10 || snap[2*32 +:32]!=2 || snap[3*32 +:32]!=1 || snap[4*32 +:32]!=1 ||
     snap[5*32 +:32]!=1 || snap[6*32 +:32]!=10 || snap[7*32 +:32]!=10 ||
     snap[8*32 +:32]!=10 || snap[9*32 +:32]!=20 || snap[15*32 +:32]!=2 ||
     snap[0 +:32]!=32'h52580103 || snap[12*32 +:32]!=1)$fatal(1,"counter/snapshot mismatch %h",snap);
  @(negedge rx_clk);d=32'hbc000000;k=8;
  @(negedge rx_clk);d=32'h00000050;k=0;
  @(negedge rx_clk);d=32'h000028bc;k=1;
  @(negedge rx_clk);d=0;k=9;
  repeat(64)@(negedge hclk);
  if(snap[10*32 +:32]!=1 || snap[11*32 +:32]!=1)$fatal(1,"K-qualified cross-word/in-word pair counters");
  @(negedge rx_clk);en=0;repeat(64)@(negedge hclk);
  if(snap[14*32 +:32]!=1)$fatal(1,"link loss snapshot");
  rst=0;repeat(8)@(negedge hclk);rst=1;repeat(64)@(negedge hclk);
  if(snap[1*32 +:32]!=0 || snap[14*32 +:32]!=0)$fatal(1,"reset snapshot");
  $display("PASS DIAGNOSTICS counters, frame snapshots, link loss, reset and asynchronous bundled CDC");$finish;
 end
 initial begin #100000;$fatal(1,"timeout");end
endmodule
