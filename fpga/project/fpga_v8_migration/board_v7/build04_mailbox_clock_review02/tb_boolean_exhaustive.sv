`timescale 1ns/1ps
module tb_boolean_exhaustive;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,clear=0,seed=0,inc=0,vs=0,oldvs=0,href=0;
 wire [15:0] oq,nq,og,ng,onext,nnext;
 old_v7_sfd_counter #(.W(16)) a(clk,rst,clear,seed,inc,oq,onext);
 new_v7_sfd_counter #(.W(16)) b(clk,rst,clear,seed,inc,nq,nnext);
 old_v7_sfd_counter #(.W(16)) c(clk,rst,(vs & !oldvs)|href,1'b0,inc,og,);
 new_v7_camera_gap_boolean d(clk,rst,vs,oldvs,href,inc,ng);
 integer n,k;reg [15:0] expected;
 initial begin
  repeat(2)@(negedge clk);rst=0;
  for(n=0;n<65536;n=n+1)for(k=0;k<8;k=k+1)begin
   @(negedge clk);{clear,seed,inc}=k[2:0];a.q=n;b.q=n;
   a.prefix={(&a.q[11:0]),(&a.q[7:0]),(&a.q[3:0])};b.prefix=a.prefix;
   expected=clear?{15'b0,seed}:(n+inc);
   #1;if(onext!==nnext || nnext!==(16'(n+inc)))$fatal(1,"next mismatch");
   @(posedge clk);#1;if(oq!==nq || nq!==expected || a.prefix!==b.prefix || b.prefix!=={(&nq[11:0]),(&nq[7:0]),(&nq[3:0])})$fatal(1,"counter mismatch");
  end
  $display("PASS build01/build04 counter exhaustive524288 transitions");
  for(n=0;n<65536;n=n+1)for(k=0;k<16;k=k+1)begin
   @(negedge clk);{vs,oldvs,href,inc}=k[3:0];c.q=n;d.q=n;
   c.prefix={(&c.q[11:0]),(&c.q[7:0]),(&c.q[3:0])};d.prefix=c.prefix;
   expected=((vs & !oldvs)|href)?16'b0:(n+inc);
   @(posedge clk);#1;if(og!==ng || ng!==expected || c.prefix!==d.prefix || d.prefix!=={(&ng[11:0]),(&ng[7:0]),(&ng[3:0])})$fatal(1,"gap mismatch");
  end
  $display("PASS build01/build04 gap exhaustive1048576 transitions");$finish;
 end
endmodule
