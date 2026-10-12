`timescale 1ns/1ps
module tb_old_default;
 reg free_clk=0;always #20 free_clk=~free_clk;
 wire clk,rst_n,en,raw_en;wire [31:0] d,raw_d;wire [3:0] k,raw_k;
 wire vs,hs,de,overflow,malformed;wire [15:0] pix;
 sfp_rx_link dut(.i_free_clk(free_clk),.i_refckp(0),.i_refckn(0),.i_l2rxn(0),.i_l2rxp(0),
 .o_rx_clk(clk),.o_rx_rst_n(rst_n),.o_rx_en(en),.o_rxd(d),.o_rxk(k),
 .o_raw_d(raw_d),.o_raw_k(raw_k),.o_raw_en(raw_en));
 sfp_decode_select selected(
 .sfp_rx_clk(clk),.sfp_rx_rst_n(rst_n),.sfp_rx_en(en),.sfp_raw_en(raw_en),
 .sfp_rxd(d),.sfp_rxk(k),.sfp_raw_d(raw_d),.sfp_raw_k(raw_k),
 .sfp_vs(vs),.sfp_hs(hs),.sfp_de(de),.sfp_pix(pix),
 .sfp_parser_overflow(overflow),.sfp_malformed(malformed));
 reg axi_clk=0;always #3.809524 axi_clk=~axi_clk;
 wire vs5,hs5,de5,vs6,hs6,de6;wire [15:0] p5,p6;
 sfp_rx_cam_if split(.i_rx_clk(clk),.i_rx_rst_n(rst_n),.i_vs(vs),.i_hs(hs),.i_de(de),.i_pix(pix),
 .i_axi_clk(axi_clk),.i_axi_rst_n(rst_n),.o_vs5(vs5),.o_hs5(hs5),.o_de5(de5),.o_pix5(p5),
 .o_vs6(vs6),.o_hs6(hs6),.o_de6(de6),.o_pix6(p6));
 reg [15:0] image[0:614399];
 integer n5=0,n6=0,s5=0,s6=0,frames=0,errors=0;
 reg pv5=0,pv6=0,check=0;integer idx;
 reg badrun=0;integer bad5=0,bad6=0;
 always @(posedge axi_clk)if(rst_n && badrun)begin
  if(de5)bad5=bad5+1;if(de6)bad6=bad6+1;
 end
 always @(posedge axi_clk) if(rst_n && check)begin
  if(vs5 && !pv5)begin
   if(s5 && n5!=307200)$fatal(1,"CAM5 prior count %0d",n5);
   n5=0;s5=s5+1;
  end
  if(vs6 && !pv6)begin
   if(s6 && n6!=307200)$fatal(1,"CAM6 prior count %0d",n6);
   n6=0;s6=s6+1;
  end
  pv5=vs5;pv6=vs6;
  if(de5)begin idx=(n5/640)*1280+n5%640;
   if(n5>=307200 || p5!==image[idx])$fatal(1,"CAM5 identity index=%0d got=%h",n5,p5);
   n5=n5+1;end
  if(de6)begin idx=(n6/640)*1280+640+n6%640;
   if(n6>=307200 || p6!==image[idx])$fatal(1,"CAM6 identity index=%0d got=%h",n6,p6);
   n6=n6+1;end
  if(split.fif5_full || split.fif6_full)$fatal(1,"split FIFO overflow");
 end
 always @(posedge clk)if(check && overflow)$fatal(1,"parser overflow");
 task replay(input string name);
 integer f,rc;reg [31:0] wd;reg [3:0] wk;
 begin
  f=$fopen(name,"r");if(!f)$fatal(1,"vector open");
  while(!$feof(f))begin rc=$fscanf(f,"%h %h\n",wd,wk);if(rc==2)begin
   @(negedge clk);dut.u_hsst.drive_d=wd;dut.u_hsst.drive_k=wk;
  end end
  $fclose(f);repeat(128)@(negedge clk);
 end endtask
 task partial(input string name);
 integer f,rc,j;reg [31:0] wd;reg [3:0] wk;
 begin
  f=$fopen(name,"r");if(!f)$fatal(1,"partial vector open");
  for(j=0;j<2000;j=j+1)begin rc=$fscanf(f,"%h %h\n",wd,wk);if(rc!=2)$fatal(1,"short partial");
   @(negedge clk);dut.u_hsst.drive_d=wd;dut.u_hsst.drive_k=wk;
  end
  $fclose(f);
 end endtask
 integer loss;
 initial begin
  $readmemh("../sfp_payload_probe/input.hex",image);
  dut.por_cnt=18'd249999;repeat(12)@(negedge clk);dut.u_hsst.lane_done=1;
  repeat(16)@(negedge clk);check=1;
  replay("../sfp_payload_probe/baseline.vec");
  if(n5!=307200 || n6!=307200 || s5!=1 || s6!=1 || malformed)$fatal(1,"old default baseline");
  $display("PASS OLD default parser CAM5/CAM6 exact 307200");$finish;
 end
 initial begin #50000000;$fatal(1,"timeout");end
endmodule
