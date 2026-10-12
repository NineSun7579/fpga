`timescale 1ns/1ps
module tb_cam34_frames;
parameter W=640,H=480;
reg clk=0,rst=1,valid=0,hs=0,vs=0;reg[15:0]pix=0;wire ov,oh,ofs;wire[15:0]op;
cam34_downsample_2x2 #(.IN_W(W),.IN_H(H)) dut(.clk(clk),.rst(rst),.in_valid(valid),.in_pixel(pix),.in_hsync(hs),.in_vsync(vs),.out_valid(ov),.out_pixel(op),.out_hsync(oh),.out_vsync(ofs));
always #5 clk=~clk;
integer frame_id=0,out_index=0,checking=0,i,j,mode=0;
function [15:0] pattern(input integer index,input integer f);
 integer x,y;begin x=index%W;y=index/W;pattern={5'((x*7+y*3+f*11)%32),6'((x*3+y*5+f*17)%64),5'((x+y*9+f*13)%32)};end
endfunction
function[15:0] reference(input integer idx,input integer f);
 integer x,y,n,r,g,b,v,a,c,d;begin
 x=(idx%(W/2))*2;y=(idx/(W/2))*2;r=0;g=0;b=0;
 for(n=0;n<4;n=n+1)begin v=pattern((y+n/2)*W+x+n%2,f);a=(v>>11)&31;c=(v>>5)&63;d=v&31;r=r+((a<<3)|(a>>2));g=g+((c<<2)|(c>>4));b=b+((d<<3)|(d>>2));end
 r=(r+2)/4;g=(g+2)/4;b=(b+2)/4;reference=((r>>3)<<11)|((g>>2)<<5)|(b>>3);
 end endfunction
always @(negedge clk)if(ov && checking)begin
 if(out_index>=W*H/4)$fatal(1,"extra pixel/dummy frame=%0d output=%0d",frame_id,out_index);
 if(op!==reference(out_index,frame_id))$fatal(1,"pixel mismatch frame=%0d index=%0d expected=%h got=%h",frame_id,out_index,reference(out_index,frame_id),op);
 out_index=out_index+1;
end
task begin_frame(input integer f);
 begin checking=0;valid=0;hs=0;@(negedge clk);vs=1;repeat(8)@(negedge clk);vs=0;repeat(8)@(negedge clk);frame_id=f;out_index=0;checking=1;end
endtask
task drive(input integer n,input integer noise);
 begin
 for(i=0;i<n;i=i+1)begin
  @(negedge clk);valid=1;pix=pattern(i,frame_id);hs=(i%W)<W-4;
  if(noise && ((i%11)==0 || (i%97)==0))begin @(negedge clk);valid=0;hs=~hs;repeat(2)@(negedge clk);end
 end
 @(negedge clk);valid=0;hs=0;repeat(8)@(negedge clk);
 end
endtask
initial begin
 repeat(8)@(negedge clk);rst=0;
 begin_frame(1);drive(W*H,0);if(out_index!=W*H/4)$fatal(1,"complete frame output quota %0d",out_index);
 $display("[PASS] complete %0dx%0d frame, pixels=%0d",W,H,out_index);
 begin_frame(2);drive(W*H,1);if(out_index!=W*H/4)$fatal(1,"gaps changed output quota %0d",out_index);
 $display("[PASS] pixel-valid gaps and unrelated HS levels preserve raster order");
 // Extra camera tail pixels are ignored and cannot extend the committed frame.
 @(negedge clk);valid=1;pix=16'hffff;repeat(5)@(negedge clk);valid=0;repeat(8)@(negedge clk);
 if(out_index!=W*H/4)$fatal(1,"dummy pixels counted");
 $display("[PASS] camera-tail dummy ignored");
 begin_frame(3);drive(W*3+5,1);checking=0;
 begin_frame(4);drive(W*H,1);if(out_index!=W*H/4)$fatal(1,"short-frame recovery quota %0d",out_index);
 $display("[PASS] VS resets raster state after interrupted frame");
 $display("CAM34_FULLFRAME_PASS bytes=%0d",W*H/2);$finish;
end
initial begin #20000000;$fatal(1,"timeout");end
endmodule
