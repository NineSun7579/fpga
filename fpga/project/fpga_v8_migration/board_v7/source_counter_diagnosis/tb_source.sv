`timescale 1ns/1ps
// FIFO is deliberately stubbed: source accounting and snapshot only.
module ov5640_cdc_fifo(input wr_clk,wr_rst,wr_en,input [15:0] wr_data,
 output wr_full,input rd_clk,rd_en,output [15:0] rd_data,output rd_empty,
 input rd_rst,output almost_full,almost_empty);
 reg test_full=0;
 assign wr_full=test_full; assign rd_empty=1; assign rd_data=0;
 assign almost_full=0; assign almost_empty=1;
endmodule
module tb_source;
 reg clk=0,vc=0,rst=1; always #5 clk=~clk; always #3.7 vc=~vc;
 reg valid=0,vs=0,href=0,rawvs=0; reg [7:0] data=0;
 wire cv,ch,cs; wire [15:0] cd;
 cmos_capture cap(.rst_n(!rst),.cam_pclk(clk),.cam_vsync(rawvs),.cam_href(href),.cam_data(data),
 .cmos_frame_valid(cv),.cmos_frame_href(ch),.cmos_frame_vsync(cs),.cmos_frame_data(cd));
 reg use_cap=0;
 // Match ov5640_tc03_binding.v:354-359 half-cycle staging.
 reg cv_r=0,cs_r=0; always @(negedge clk) begin cv_r<=cv;cs_r<=cs;end
 wire sv=use_cap?cv_r:valid, ss=use_cap?cs_r:vs;
 wire [31:0] di,dd,dseq;
 ov5640_cdc_tc04 #(.DATA_WIDTH(16)) dut(.cam_clk(clk),.cam_rst(rst),.s_data(cd),
 .s_valid(sv),.s_hsync(ch),.s_vsync(ss),.video_clk(vc),.video_rst(rst),
 .dbg_cdc_input(di),.dbg_cdc_drop(dd),.dbg_cdc_seq(dseq),.dbg_cdc_output(),
 .video_data(),.video_valid(),.video_hsync(),.video_vsync());
 reg prev=0; reg [31:0] ref_count=0,ref_drop=0,ref_seq=0;
 reg [95:0] ref_snap=0; integer checks=0,j;
 integer cap_total=0; reg monitoring=0;
 always @(posedge clk) begin
  if(rst) begin prev=0;ref_count=0;ref_drop=0;ref_seq=0;ref_snap=0;end
  else begin
   if(ss&&!prev) begin ref_seq=ref_seq+1;ref_snap={ref_seq,ref_drop,ref_count};ref_count=sv;ref_drop=sv&&dut.full;end
   else begin ref_count=ref_count+sv;ref_drop=ref_drop+(sv&&dut.full);end
   prev=ss;
   if(monitoring&&cv) cap_total=cap_total+1;
  end
  #0.01;
  if(dut.src_count!==ref_count || dut.src_drop!==ref_drop || dut.src_snapshot!==ref_snap) $fatal(1,"source mismatch");
  for(j=1;j<8;j=j+1) begin
   if(dut.count_prefix[j]!==((ref_count & (32'hffffffff >> (32-4*j)))==(32'hffffffff >> (32-4*j)))) $fatal(1,"count prefix");
   if(dut.drop_prefix[j]!==((ref_drop & (32'hffffffff >> (32-4*j)))==(32'hffffffff >> (32-4*j)))) $fatal(1,"drop prefix");
  end
  checks=checks+1;
 end
 task tick(input bit v,input bit s); begin @(negedge clk);valid=v;vs=s;end endtask
 task idle(input integer n); repeat(n) tick(0,0); endtask
 task rawtick(input bit h,input bit s); begin @(negedge clk);href=h;rawvs=s;data=data+1;end endtask
 task frame(input integer short_lines); integer y,x;begin
  cap_total=0;monitoring=1;
  for(y=0;y<480;y=y+1) begin
   for(x=0;x<(y<short_lines?1279:1280);x=x+1) rawtick(1,0);
   repeat(8) rawtick(0,0);
  end
  repeat(12) rawtick(0,0);
  monitoring=0;
  if(cap_total!=307200-short_lines) $fatal(1,"capture count %0d",cap_total);
  rawtick(0,1);repeat(8) rawtick(0,1);repeat(12) rawtick(0,0);
  if(di!=307200-short_lines || dd!=0) $fatal(1,"capture snapshot %0d",di);
  $display("PASS capture short_lines=%0d valid=%0d snapshot=%0d drop=%0d",short_lines,cap_total,di,dd);
 end endtask
 integer i,k,n; reg [31:0] rng=32'h12345678; reg [31:0] seed_value;
 initial begin
  repeat(5) @(negedge clk);rst=0;
  // Continuous, alternating, sparse and deterministic pseudorandom valid/full.
  for(k=0;k<4;k=k+1) begin
   tick(0,1);idle(10);
   for(i=0;i<70000;i=i+1) begin
    rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
    tick(k==0?1:k==1?i%2:k==2?i%17==0:rng[0],0);
    dut.ov5640_cdc_fifo.test_full=(k==0?1:rng[4]);
   end
   idle(2);tick(0,1);idle(12);
   if({dseq,dd,di}!==ref_snap) $fatal(1,"snapshot mismatch");
   $display("PASS pattern=%0d count=%0d drop=%0d",k,di,dd);
  end
  dut.ov5640_cdc_fifo.test_full=0;
  tick(0,1);idle(8); repeat(31) tick(1,0);
  tick(1,1);idle(12);
  if(di!=31 || dut.src_count!=1) $fatal(1,"boundary ownership");
  $display("PASS boundary previous=31 next=1 total=32 (no lost valid)");
  tick(0,1);idle(8);repeat(307199) tick(1,0);
  tick(1,1);idle(12);
  if(di!=307199 || dut.src_count!=1) $fatal(1,"full-size boundary");
  repeat(307200) tick(1,0);idle(2);tick(0,1);idle(12);
  if(di!=307201) $fatal(1,"window compensation");
  $display("PASS window transfer snapshots=307199,307201 total=614400");
  // Deposit consistent pre-state near every nibble boundary, including wrap.
  // This avoids billions of cycles and still exercises the original sequential RTL.
  for(n=1;n<=8;n=n+1) begin
   @(negedge clk);valid=0;vs=0;
   seed_value=(32'hffffffff >> (32-4*n))-8;
   dut.src_count=seed_value;dut.src_drop=seed_value;
   ref_count=seed_value;ref_drop=seed_value;
   for(i=1;i<8;i=i+1) begin
    dut.count_prefix[i]=((seed_value & (32'hffffffff >> (32-4*i)))==(32'hffffffff >> (32-4*i)));
    dut.drop_prefix[i]=dut.count_prefix[i];
   end
   dut.ov5640_cdc_fifo.test_full=1;
   repeat(20) tick(1,0);idle(2);
   $display("PASS seeded nibble=%0d final=%h",n,dut.src_count);
  end
  dut.ov5640_cdc_fifo.test_full=0;
  // Default WAIT_FRAME=10: exercise real startup, no parameter override.
  @(negedge clk);rst=1;use_cap=1;valid=0;vs=0;
  repeat(5) @(negedge clk);rst=0;
  repeat(11) begin repeat(5) rawtick(0,1);repeat(8) rawtick(0,0);end
  if(!cap.frame_val_flag) $fatal(1,"startup");
  frame(0);frame(1);frame(2);frame(7);
  // Raw VSYNC overlapping every position of a 16-byte line does not gate valid.
  for(k=0;k<=16;k=k+1) begin
   cap_total=0;monitoring=1;
   for(i=0;i<16;i=i+1) rawtick(1,i>=k);
   repeat(12) rawtick(0,1);repeat(12) rawtick(0,0);
   monitoring=0;
   if(cap_total!=8) $fatal(1,"overlap lost valid offset=%0d",k);
  end
  $display("PASS raw VSYNC overlap offsets=0..16 total_valid=8 each");
  // Same 1280 accepted bytes, but odd-length HREF fragments discard two tails.
  cap_total=0;monitoring=1;
  rawtick(1,0);rawtick(0,0);repeat(1279) rawtick(1,0);repeat(12) rawtick(0,0);
  monitoring=0;
  if(cap_total!=639) $fatal(1,"fragmentation expected 639");
  $display("EXPECTED_LIMIT HREF fragments=1+1279 accepted_bytes=1280 valid=639 (true valid deficit)");
  $display("ALL_PASS source_checks=%0d",checks);$finish;
 end
 initial begin #100000000;$fatal(1,"timeout");end
endmodule
