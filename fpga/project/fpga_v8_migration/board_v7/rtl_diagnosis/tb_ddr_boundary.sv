`timescale 1ns/1ps
module tb_ddr_boundary;
 localparam N=307200;
 reg clk=0; always #5 clk=~clk;
 reg rst=1,valid=0,vs=0;
 reg [15:0] data=0;
 wire [31:0] source_count,rejects,fault;
 wire av,al;
 wire [127:0] ad;
 integer accepted=0,beats=0,errors=0,checks=0;
 integer delta,i,t,last,sof_at,expected,first_gap,extra,kind;
 ov5640_ddr_tc04 #(.DATA_WIDTH(16),.CAM_DATA_LEN(38400)) dut(
  .axi_clk(clk),.axi_rst(rst),.dma_abort(1'b0),.dma_done(1'b0),
  .axi_cam_en(1'b1),.cam_data_addr_1(32'h1800000),.cam_data_addr_2(32'h1a00000),
  .cam_data_len(17'd38400),.s_data(data),.s_data_valid(valid),.s_hsync(1'b0),.s_vsync(vs),
  .axi_data(ad),.axi_data_valid(av),.axi_data_last(al),.axi_data_ready(1'b1),
  .axi_cmd_ready(1'b1),.xdma_ack(2'b0),.dbg_fault_snapshot(fault),
  .dbg_reject_counts(rejects),.dbg_input_pixels(source_count),
  .dma_abort_req(),.axi_data_available(),.axi_cmd_addr(),.axi_cmd_len(),
  .axi_cmd_valid(),.xdma_req(),.dbg_axi_cnt(),.dbg_axi_num(),.dbg_zdin(),
  .dbg_zout(),.dbg_state(),.dbg_last_cnt(),.dbg_wd_cnt(),.prev_frame_base());
 always @(posedge clk) begin
  if(rst) begin accepted=0;beats=0;end
  else begin
   if(dut.m_data_valid) accepted=accepted+1;
   if(av) beats=beats+1;
  end
 end
 task tick(input bit v,input bit s);
  begin @(negedge clk);valid=v;vs=s;data=data+1;@(posedge clk);#1;end
 endtask
 task reset_frame;
  begin
   @(negedge clk);rst=1;valid=0;vs=0;
   repeat(5) @(posedge clk);
   @(negedge clk);rst=0;
   repeat(8) tick(0,0);
  end
 endtask
 task check(input bit condition,input string label);
  begin checks=checks+1;if(!condition) begin errors=errors+1;$display("FAIL %s",label);end end
 endtask
 initial begin
  // delta = next raw_sof sample minus final real valid sample.
  // Final seven real pixels are consecutive, exposing exact lost counts.
  for(delta=-3;delta<=3;delta=delta+1) begin
   reset_frame();tick(0,1);repeat(12) tick(0,0);
   for(i=0;i<N-7;i=i+1) tick(1,0);
   for(t=0;t<16;t=t+1) tick(t<7,t==6+delta);
   expected=delta>0 ? N : N-1+delta;
   $display("BOUNDARY delta=%0d source=%0d accepted=%0d pixel=%0d shorts=%0d overflow=%0d good=%0d beats=%0d",delta,source_count,accepted,dut.pixel_count,rejects[15:0],rejects[31:16],dut.frame_good,beats);
   check(accepted==expected,"boundary accepted");
   check(source_count==expected,"boundary source excludes SOF-cycle valid");
   check(rejects[15:0]==(delta<=0 ? 1:0),"boundary shorts");
   check(rejects[31:16]==0,"boundary no overflow");
   check(dut.frame_good==(delta>0),"boundary good");
  end
  // Correctly spaced complete frame, optional camera tail dummy.
  for(extra=0;extra<=1;extra=extra+1) begin
   reset_frame();tick(0,1);repeat(12) tick(0,0);
   for(i=0;i<N+extra;i=i+1) tick(1,0);
   repeat(12) tick(0,0);tick(0,1);repeat(12) tick(0,0);
   $display("NORMAL extra_dummy=%0d source=%0d accepted=%0d shorts=%0d good=%0d beats=%0d",extra,source_count,accepted,rejects[15:0],dut.frame_good,beats);
   check(source_count==N+extra,"normal source");check(accepted==N,"normal bounded accepted");
   check(rejects==0 && dut.frame_good && beats==38400,"normal complete");
  end
  // A dummy at raw_sof is safe if every REAL pixel preceded the marker.
  for(delta=-1;delta<=1;delta=delta+1) begin
   reset_frame();tick(0,1);repeat(12) tick(0,0);
   for(i=0;i<N-2;i=i+1) tick(1,0);
   for(t=0;t<16;t=t+1) tick(t<3,t==2+delta);
   expected=delta<0 ? N-1 : N;
   $display("DUMMY_BOUNDARY delta=%0d source=%0d accepted=%0d shorts=%0d good=%0d",delta,source_count,accepted,rejects[15:0],dut.frame_good);
   check(source_count==N+delta,"dummy source");
   check(accepted==expected,"dummy accepted");
   check(rejects==(delta<0 ? 1:0),"dummy boundary shorts");
  end
  // Real deficit controls, matching board source values, with safe VSYNC gap.
  for(kind=0;kind<3;kind=kind+1) begin
   expected=kind==0 ? N-1 : (kind==1 ? N-2 : N-7);
   reset_frame();tick(0,1);repeat(12) tick(0,0);
   for(i=0;i<expected;i=i+1) tick(1,0);
   repeat(12) tick(0,0);tick(0,1);repeat(12) tick(0,0);
   $display("DEFICIT sent=%0d source=%0d accepted=%0d shorts=%0d fault=%h",expected,source_count,accepted,rejects[15:0],fault);
   check(source_count==expected && accepted==expected && rejects==1,"deficit correctly short");
  end
  // Full 307200 valids between raw SOFs but first valid too near admitted SOF.
  for(first_gap=0;first_gap<=3;first_gap=first_gap+1) begin
   reset_frame();tick(0,1);repeat(first_gap) tick(0,0);
   for(i=0;i<N;i=i+1) tick(1,0);
   repeat(12) tick(0,0);tick(0,1);repeat(12) tick(0,0);
   expected=N-(first_gap<2 ? 2-first_gap : 0);
   $display("START gap=%0d source=%0d accepted=%0d pixel=%0d shorts=%0d good=%0d",first_gap,source_count,accepted,dut.pixel_count,rejects[15:0],dut.frame_good);
   check(source_count==N && accepted==expected,"start gating");
   check(rejects==(first_gap<2 ? 1:0),"start shorts");
  end
  $display("DDR_BOUNDARY_DONE checks=%0d errors=%0d",checks,errors);
  if(errors) $fatal(1,"RTL assertion failures");
  $finish;
 end
endmodule
