`timescale 1ns/1ps
module tb_cam34_downsample;
  localparam IN_W=4, IN_H=4;
  reg clk=0,rst=1,in_valid=0,in_hsync=0,in_vsync=0;
  reg [15:0] in_pixel=0;
  wire out_valid,out_hsync,out_vsync;
  wire [15:0] out_pixel;
  integer out_count=0;
  reg [15:0] expected [0:3];
  integer x,y;
  cam34_downsample_2x2 #(.IN_W(IN_W),.IN_H(IN_H)) dut(
    .clk(clk),.rst(rst),.in_valid(in_valid),.in_pixel(in_pixel),
    .in_hsync(in_hsync),.in_vsync(in_vsync),.out_valid(out_valid),
    .out_pixel(out_pixel),.out_hsync(out_hsync),.out_vsync(out_vsync));
  always #5 clk=~clk;
  task send_pixel(input integer xx,input integer yy,input [15:0] p);
    begin @(negedge clk); in_valid=1;in_pixel=p; end
  endtask
  task send_row(input integer yy);
    begin @(negedge clk); in_hsync=1; for(x=0;x<IN_W;x=x+1) send_pixel(x,yy,(x << 11) | (yy << 5) | ((x+yy) & 31)); @(negedge clk); in_valid=0;in_hsync=0; end
  endtask
  initial begin
    // Filled below from the same RGB565 expanded-channel 2x2 mean as the DUT.
    expected[0]=16'h0001; expected[1]=16'h1003; expected[2]=16'h0043; expected[3]=16'h1045;
    repeat(3) @(negedge clk); rst=0;
    @(negedge clk); in_vsync=1; @(negedge clk); in_vsync=0;
    for(y=0;y<IN_H;y=y+1) send_row(y);
    repeat(10) @(negedge clk);
    if(out_count!==4) $fatal(1,"expected four output pixels, got %0d",out_count);
    $display("CAM34_DOWNSAMPLE_PASS"); $finish;
  end
  always @(posedge clk) if(out_valid) begin
    if(out_count<4 && out_pixel!==expected[out_count]) $fatal(1,"pixel %0d expected %h got %h",out_count,expected[out_count],out_pixel);
    out_count=out_count+1;
  end
endmodule
