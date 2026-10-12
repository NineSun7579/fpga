`timescale 1ns/1ps
module tb_gap_exhaustive;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,vs=0,oldvs=0,href=0,inc=0;
 wire clear=(vs & !oldvs)|href;
 wire [15:0] golden,candidate;
 golden_sfd_counter #(.W(16)) g(clk,rst,clear,1'b0,inc,golden,);
 v7_camera_gap_boolean c(clk,rst,vs,oldvs,href,inc,candidate);
 integer n,k;reg [15:0] expected;
 initial begin
   repeat(2)@(negedge clk);rst=0;
   for(n=0;n<65536;n=n+1)for(k=0;k<16;k=k+1)begin
     @(negedge clk);{vs,oldvs,href,inc}=k[3:0];g.q=n;c.q=n;
     g.prefix={(&g.q[11:0]),(&g.q[7:0]),(&g.q[3:0])};c.prefix=g.prefix;
     expected=((vs & !oldvs)|href)?16'b0:(n+inc);
     @(posedge clk);#1;
     if(golden!==candidate || candidate!==expected ||
       g.prefix!==c.prefix || c.prefix!=={(&candidate[11:0]),(&candidate[7:0]),(&candidate[3:0])})
       $fatal(1,"gap exhaustive fail state=%h controls=%h",n,k);
   end
   $display("PASS actual golden/candidate gap exhaustive 1048576 state/control transitions");
   $finish;
 end
endmodule
