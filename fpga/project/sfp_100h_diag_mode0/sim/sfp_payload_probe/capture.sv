`timescale 1ns/1ps
module capture;
 reg fab_clk=0,vid_clk=0,rst_n=0;
 always #4 fab_clk=~fab_clk;
 always @(negedge fab_clk) vid_clk<=~vid_clk;
 reg [18:0] video=0;
 wire [31:0] txd; wire [3:0] txk;
 sfp_video_tx tx(.vid_clk(vid_clk),.vid_rst_n(rst_n),.vid_data(video),
 .fab_clk(fab_clk),.fab_rst_n(rst_n),.link_ready(rst_n),.txd(txd),.txk(txk));
 reg [15:0] image[0:614399];
 integer out,y,x,n=0;
 always @(negedge fab_clk) if(rst_n) $fdisplay(out,"%08h %h",txd,txk);
 task symbol(input bit v,d,input [15:0] p);
 begin @(negedge vid_clk);video={v,1'b0,d,p};end endtask
 initial begin
  $readmemh("input.hex",image);out=$fopen("actual.vec","w");
  #101;rst_n=1;
  repeat(32) symbol(0,0,0);
  repeat(4) symbol(1,0,0);
  repeat(8) symbol(0,0,0);
  for(y=0;y<480;y=y+1) begin
   for(x=0;x<1280;x=x+1) begin symbol(0,1,image[n]);n=n+1;end
   repeat(648) symbol(0,0,0);
  end
  repeat(128) symbol(0,0,0);
  $fclose(out);$display("CAPTURE pixels=%0d",n);$finish;
 end
 initial begin #40000000;$fatal(1,"timeout");end
endmodule
