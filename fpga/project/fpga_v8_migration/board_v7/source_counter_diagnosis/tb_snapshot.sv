`timescale 1ns/1ps
module tb_snapshot;
 reg clk=0,vc=0,rst=1,v=0,s=0;
 always #1 clk=~clk;
 always #5 vc=~vc;
 wire [31:0] di,dd,ds;
 ov5640_cdc_tc04 #(.DATA_WIDTH(16)) dut(.cam_clk(clk),.cam_rst(rst),.s_data(16'b0),
 .s_valid(v),.s_hsync(1'b0),.s_vsync(s),.video_clk(vc),.video_rst(rst),
 .dbg_cdc_input(di),.dbg_cdc_drop(dd),.dbg_cdc_seq(ds),.dbg_cdc_output(),
 .video_data(),.video_valid(),.video_hsync(),.video_vsync());
 reg [95:0] history[0:1023]; integer published=0,updates=0,skipped=0;
 reg [31:0] lastseq=0; reg [95:0] last_source=0;
 always @(negedge clk) if(!rst && dut.src_snapshot!==last_source) begin
  last_source=dut.src_snapshot;history[dut.src_seq]=dut.src_snapshot;published=published+1;
 end
 always @(negedge vc) if(!rst && ds!=lastseq) begin
  if({ds,dd,di}!==history[ds]) $fatal(1,"torn tuple");
  if(ds!=lastseq+1) skipped=skipped+1;
  lastseq=ds;updates=updates+1;
 end
 task tick(input bit a,input bit b);begin @(negedge clk);#0.1;v=a;s=b;end endtask
 integer i,j;
 initial begin
  history[0]=0;repeat(8) tick(0,0);rst=0;
  for(i=0;i<30;i=i+1) begin
   tick(1,1);for(j=0;j<50+i;j=j+1) tick(j%3!=0,0);
  end
  repeat(40) tick(0,0);
  if(updates!=published || skipped!=0) $fatal(1,"normal snapshot loss");
  $display("PASS snapshot stable published=%0d received=%0d torn=0",published,updates);
  // No acknowledgement exists: deliberately violate the frame-spacing assumption.
  for(i=0;i<100;i=i+1) begin tick(i%2,1);tick(1,0);end
  repeat(80) tick(0,0);
  if(updates>=published || skipped==0) $fatal(1,"stress did not expose toggle alias");
  $display("EXPECTED_LIMIT snapshot rapid published=%0d received=%0d sequence_jumps=%0d torn=0",published,updates,skipped);
  $display("SNAPSHOT_ALL_PASS");$finish;
 end
endmodule
