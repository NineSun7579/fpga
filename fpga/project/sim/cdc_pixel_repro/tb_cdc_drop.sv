`timescale 1ns/1ps
module tb_cdc_drop;
reg cc=0,vc=0,rst=1,valid=0,vs=0;
always #5.952381 cc=~cc;
always #3.809524 vc=~vc;
reg [15:0] data=0;
wire ov;
wire [15:0] od;
wire [31:0] di,dout,drop,seq;
integer sent=0,received=0,i;
reg [15:0] expected[0:119];
ov5640_cdc #(.DATA_WIDTH(16)) dut(.cam_clk(cc),.cam_rst(rst),
 .video_clk(vc),.video_rst(rst),.s_data(data),.s_valid(valid),.s_hsync(1'b0),.s_vsync(vs),
 .video_valid(ov),.video_data(od),.video_hsync(),.video_vsync(),
 .dbg_cdc_input(di),.dbg_cdc_output(dout),.dbg_cdc_drop(drop),.dbg_cdc_seq(seq));
GTP_GRS GRS_INST(.GRS_N(1'b1));
always @(posedge vc) if(!rst && ov) begin
 if(received>=sent || od!==expected[received]) $fatal(1,"Drop/recovery data mismatch");
 received=received+1;
end
task mark;
 begin
  repeat(30) @(negedge vc);
  @(negedge cc); vs=1;
  repeat(20) @(negedge cc);
  vs=0;
  repeat(20) @(negedge cc);
 end
endtask
task pixel(input integer n,input bit rejected);
 begin
  @(negedge cc); valid=1;data=n;
  if(!rejected) begin expected[sent]=n;sent=sent+1;end
  @(negedge cc); valid=0;
 end
endtask
initial begin
 #100; @(negedge cc); rst=0;mark();
 for(i=0;i<40;i=i+1)pixel(i,0);
 force dut.full=1'b1;
 for(i=40;i<60;i=i+1)pixel(i,1);
 release dut.full;
 for(i=60;i<100;i=i+1)pixel(i,0);
 mark();
 if(di!==100 || dout!==80 || drop!==20 || seq!==2)
  $fatal(1,"Drop snapshot %0d %0d %0d %0d",di,dout,drop,seq);
 for(i=100;i<120;i=i+1)pixel(i,0);
 mark();
 if(di!==20 || dout!==20 || drop!==0 || seq!==3 || received!=100)
  $fatal(1,"Recovery snapshot %0d %0d %0d %0d",di,dout,drop,seq);
 $display("PASS DROP diagnostic: 100 offered/80 output/20 dropped; next frame 20/20/0; exact pixels");
 $finish;
end
initial begin #100000; $fatal(1,"Timeout"); end
endmodule
