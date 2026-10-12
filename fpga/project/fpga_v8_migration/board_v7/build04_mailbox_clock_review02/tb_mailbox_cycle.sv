`timescale 1ns/1ps
module tb_mailbox_cycle;
 GTP_GRS GRS_INST(1'b1);
 wire [3:0] finished;
 genvar i;
 generate for(i=0;i<4;i=i+1) begin: cams
  review_lane #(.CAM(i)) lane(finished[i]);
 end endgenerate
 initial begin wait(&finished);$display("PASS ALL2048 mailbox and host bits against original and build01 models, four independent cameras");$finish;end
 initial begin #5000000;$fatal(1,"timeout");end
endmodule
module review_lane #(parameter CAM=0)(output reg done=0);
 reg clk=0,hclk=0;always #(5+CAM) clk=~clk;always #(9+CAM*2) hclk=~hclk;
 reg rst=1,hrst=1,rawvs=0,href=0,byteok=0,vs=0,valid=0;
 reg read=0,acquire=0,release_s=0;reg [4:0] word=0;
 wire [36:0] bo,co,oo;
 old_v7_sfd_candidate b(clk,rst,hclk,hrst,rawvs,href,byteok,vs,valid,read,acquire,release_s,word,bo[31:0],bo[32],bo[33],bo[34],bo[35],bo[36]);
 new_v7_sfd_candidate c(clk,rst,hclk,hrst,rawvs,href,byteok,vs,valid,read,acquire,release_s,word,co[31:0],co[32],co[33],co[34],co[35],co[36]);
 original_v7_sfd_candidate o(clk,rst,hclk,hrst,rawvs,href,byteok,vs,valid,read,acquire,release_s,word,oo[31:0],oo[32],oo[33],oo[34],oo[35],oo[36]);
 reg [31:0] rng=32'h61c029ab+CAM;integer cycles=0,checks=0,writes=0,captures=0,k;
 function [31:0] next_rng(input [31:0] x);reg [31:0] y;begin y=x^(x<<13);y=y^(y>>17);next_rng=y^(y<<5);end endfunction
 task compare;begin
  if(b.mailbox!==c.mailbox || b.host_bank!==c.host_bank || bo!==co || o.mailbox!==c.mailbox || o.host_bank!==c.host_bank || oo!==co)
   $fatal(1,"camera%0d cycle%0d original/build01/current mismatch",CAM,cycles);
  if(c.rst_c===1'b0 && c.edge_vs && c.armed && !c.busy) writes=writes+1;
  if(c.rst_h===1'b0 && c.snapshot_available && acquire) captures=captures+1;
  checks=checks+1;
 end endtask
 always @(posedge hclk) begin #1;if(cycles>4&&!done)compare;end
 initial begin
  repeat(5)@(negedge clk);rst=0;hrst=0;
  for(cycles=0;cycles<40000;cycles=cycles+1)begin
   @(negedge clk);rng=next_rng(rng);
   {rawvs,href,byteok,vs,valid}=rng[4:0];
   read=1;word=cycles%17;
   acquire=(cycles%7!=0);release_s=(cycles%11==0);
   rst=(cycles%997)==40;hrst=(cycles%1297)==51;
   // Successful captures, busy overrun/hold, release and all16 payload words.
   if(cycles%200<80)begin vs=(cycles%20==0);rawvs=vs;href=cycles%20>2;valid=href;byteok=href;end
   @(posedge clk);#1;compare;
  end
  if(writes<100||captures<100)$fatal(1,"insufficient snapshot coverage");
  $display("PASS camera%0d cycles=%0d observations=%0d writes=%0d captures=%0d all512 mailbox+512 host bits and bus outputs",CAM,cycles,checks,writes,captures);
  done=1;
 end
endmodule
