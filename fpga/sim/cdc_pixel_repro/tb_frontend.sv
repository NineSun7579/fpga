`timescale 1ns/1ps
module tb_frontend;
parameter real CAM_HALF=5.952380952;
parameter real PHASE=0.0;
reg pclk=0, clk=0, rst=1;
initial begin #(PHASE); forever #(CAM_HALF) pclk=~pclk; end
always #3.809523810 clk=~clk;
reg vs=0, href=0;
reg [7:0] data=0;
wire cv, ch, cs;
wire [15:0] cd;
cmos_capture #(.DATA_WIDTH(16)) capture(
 .rst_n(!rst),.cam_pclk(pclk),.cam_vsync(vs),.cam_href(href),.cam_data(data),
 .cmos_frame_vsync(cs),.cmos_frame_href(ch),.cmos_frame_valid(cv),.cmos_frame_data(cd));
reg rv, rh, rs;
reg [15:0] rd;
always @(negedge pclk) begin rv<=cv; rh<=ch; rs<=cs; rd<=cd; end
wire ov, os;
wire [15:0] od;
wire [31:0] di, dout, drop, seq;
ov5640_cdc #(.DATA_WIDTH(16)) cdc(.cam_clk(pclk),.cam_rst(rst),
 .s_data(rd),.s_valid(rv),.s_hsync(rh),.s_vsync(rs),
 .video_clk(clk),.video_rst(rst),.video_data(od),.video_valid(ov),.video_vsync(os),.video_hsync(),
 .dbg_cdc_input(di),.dbg_cdc_output(dout),.dbg_cdc_drop(drop),.dbg_cdc_seq(seq));
wire fv, fs;
wire [15:0] fd;
cam_fir3 fir(.clk(clk),.rst(rst),.in_valid(ov),.in_pixel(od),.in_vsync(os),
 .out_valid(fv),.out_vsync(fs),.out_pixel(fd));
GTP_GRS GRS_INST(.GRS_N(1'b1));
integer offered=0, captured=0, received=0, filtered=0;
integer f,y,x;
reg [15:0] pixel;
reg [15:0] expected[0:614399];
reg [15:0] fexpected[0:614399];
reg [15:0] prev1=0,prev2=0;
integer rsum,gsum,bsum;
always @(posedge pclk) if(!rst && rv) begin
 if(rd!==expected[captured]) $fatal(1,"Capture pixel %0d got=%h want=%h",captured,rd,expected[captured]);
 captured=captured+1;
 if(cdc.full) $fatal(1,"CDC unexpectedly full");
end
always @(posedge clk) if(!rst) begin
 if(ov) begin
  if(received>=captured || od!==expected[received]) $fatal(1,"CDC pixel %0d",received);
  rsum=od[15:11]+2*prev1[15:11]+prev2[15:11];
  gsum=od[10:5]+2*prev1[10:5]+prev2[10:5];
  bsum=od[4:0]+2*prev1[4:0]+prev2[4:0];
  fexpected[received]={rsum[6:2],gsum[7:2],bsum[6:2]};
  prev2=prev1; prev1=od; received=received+1;
 end
 if(fv) begin
  if(filtered>=received || fd!==fexpected[filtered]) $fatal(1,"FIR pixel %0d",filtered);
  filtered=filtered+1;
 end
end
task byte_tick(input bit h, input [7:0] d);
 begin @(negedge pclk); #0.01; href=h; data=d; end
endtask
task frame_mark;
 begin
  @(negedge pclk); #0.01; vs=1;
  repeat(20) @(negedge pclk);
  #0.01; vs=0;
  repeat(20) @(negedge pclk);
 end
endtask
initial begin
 #200; @(negedge pclk); #0.01; rst=0;
 repeat(20) @(negedge pclk);
 // Retain production's ten-frame startup discard (eleventh edge arms it).
 repeat(11) frame_mark();
 for(f=0;f<2;f=f+1) begin
  for(y=0;y<480;y=y+1) begin
   for(x=0;x<640;x=x+1) begin
    pixel=(f*123+y*640+x)^16'hc953;
    expected[offered]=pixel; offered=offered+1;
    byte_tick(1,pixel[15:8]); byte_tick(1,pixel[7:0]);
   end
   byte_tick(0,0); repeat(615) @(negedge pclk);
  end
  // Complete the sensor's 984-row period with vertical blanking.
  repeat(504*1896) @(negedge pclk);
  frame_mark();
  if(di!==307200 || dout!==307200 || drop!==0 || seq!==f+2)
   $fatal(1,"Frame snapshot f=%0d in=%0d out=%0d drop=%0d seq=%0d",f,di,dout,drop,seq);
  $display("PASS frame=%0d input=%0d output=%0d drop=%0d seq=%0d",f,di,dout,drop,seq);
 end
 if(offered!=614400 || captured!=offered || received!=offered || filtered!=offered)
  $fatal(1,"Counts %0d %0d %0d %0d",offered,captured,received,filtered);
 $display("PASS FRONTEND half=%0f phase=%0f offered=%0d captured=%0d CDC=%0d FIR=%0d",CAM_HALF,PHASE,offered,captured,received,filtered);
 $finish;
end
initial begin #200000000; $fatal(1,"Timeout"); end
endmodule
