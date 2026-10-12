`timescale 1ns/1ps
module tb_contract;
 reg cam=0,vid=0,rst=1,ven=1,v=0,valid=0;
 reg [15:0] data=0;
 always #6 cam=~cam;
 always #8 if(ven) vid=~vid;
 GTP_GRS GRS_INST(.GRS_N(1'b1));
 wire [15:0] q;wire qv,qs,fault;
 cdc_recovery #(.DATA_WIDTH(16)) dut(.system_reset(rst),.cam_clk(cam),.cam_rst(rst),
 .s_data(data),.s_valid(valid),.s_hsync(1'b0),.s_vsync(v),
 .video_clk(vid),.video_rst(rst),.video_data(q),.video_valid(qv),.video_vsync(qs),
 .boundary_fault(fault),.video_hsync(),.dbg_cdc_input(),.dbg_cdc_output(),.dbg_cdc_drop(),.dbg_cdc_seq());
 integer errors=0,ni=0,no=0,nm=0,cycle=0,last_marker=-99;
 integer marker_pixels[0:5000],mi=0;
 reg [15:0] expected[0:10000];reg prev=0,srcprev=0,checking=1;
 task check(input bit ok,input string msg);
  if(!ok) begin errors++;$display("FAIL %s",msg);end
 endtask
 always @(posedge cam) if(!rst&&checking) begin
  if(valid) begin expected[ni]=data;ni++;end
  if(v&&!srcprev) begin marker_pixels[mi]=ni;mi++;end
  srcprev=v;
 end
 always @(posedge vid) if(!rst&&checking) begin
  cycle++;
  check(!(qv&&qs),"valid overlaps VSYNC");
  if(qs&&!prev) begin
   check(nm<mi&&no==marker_pixels[nm],"marker overtook/lost pixels");
   nm++;last_marker=cycle;
  end
  if(qv) begin
   check(no<ni&&q===expected[no],"pixel conservation/order");
   check(cycle-last_marker>=3,"DDR initial admission gap");no++;
  end
  prev=qs;
 end
 task tick(input bit sv,valid_in,input [15:0] d);
  @(negedge cam);v=sv;valid=valid_in;data=d;
 endtask
 task reset_all;
  @(negedge cam);rst=1;v=0;valid=0;ven=1;
  repeat(30) @(negedge vid);
  ni=0;no=0;nm=0;mi=0;cycle=0;last_marker=-99;prev=0;srcprev=0;
  @(negedge cam);rst=0; repeat(20) tick(0,0,0);
 endtask
 integer j,k,saved;
 initial begin
  reset_all();
  // Back-to-back one-PCLK high/low markers, with small frame payloads.
  for(j=0;j<100;j++) begin
   tick(1,0,0);
   for(k=0;k<8;k++) begin tick(0,1,j*8+k);tick(0,0,0);end
  end
  tick(1,0,0);tick(0,0,0);repeat(3000) @(negedge vid);
  check(ni==800&&no==800&&nm==101&&!dut.transport_fault,"back-to-back result");
  $display("CONTRACT ordered pixels=%0d markers=%0d",no,nm);
  // Metadata-only overflow must latch even though pixel drop count is zero.
  checking=0;reset_all();@(negedge vid);ven=0;
  repeat(2200) begin tick(1,0,0);tick(0,0,0);end
  check(dut.transport_fault,"metadata full fault missing");
  ven=1;repeat(100) @(negedge vid);
  check(!qv&&fault,"fault did not stop output/export status");
  $display("CONTRACT metadata overflow latched");
  reset_all();tick(1,0,0);tick(0,0,0);@(negedge vid);ven=0;
  repeat(1100) tick(0,1,16'h1234);
  tick(0,0,0);check(dut.transport_fault,"pixel full fault missing");
  ven=1;repeat(100) @(negedge vid);check(!qv&&fault,"pixel fault did not stop/export status");
  $display("CONTRACT pixel overflow latched");
  reset_all();tick(1,1,16'h1234);tick(0,0,0);
  check(dut.transport_fault,"overlap contract violation missing");
  $display("CONTRACT invalid overlap latched");
  // Reset while data/markers queued, then restart with no old data leakage.
  reset_all();@(negedge vid);ven=0;
  tick(1,0,0);tick(0,0,0);repeat(100) tick(0,1,16'hdead);tick(0,0,0);
  reset_all();checking=1;
  tick(1,0,0);tick(0,0,0);repeat(8) tick(0,1,16'hbeef);
  tick(0,0,0);tick(1,0,0);tick(0,0,0);
  repeat(200) @(negedge vid);
  check(no==8&&nm==2&&!dut.transport_fault,"reset recovery");
  $display("CONTRACT_DONE errors=%0d",errors);
  if(errors) $fatal(1,"contract failures");$finish;
 end
endmodule
