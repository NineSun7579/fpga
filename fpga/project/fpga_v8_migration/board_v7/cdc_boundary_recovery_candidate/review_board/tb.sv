`timescale 1ns/1ps
module tb_recovery #(parameter realtime CAM_HALF=6, VID_HALF=8);
reg cam=0,vid=0,cen=1,ven=1,cr=1,vr=1,sr=1,sv=0,vs=0;
reg [15:0] data=0;
always #(CAM_HALF) if(cen) cam=~cam;
always #(VID_HALF) if(ven) vid=~vid;
GTP_GRS GRS_INST(.GRS_N(1'b1));
wire [15:0] q; wire qv,qs,fault;
cdc_recovery dut(.system_reset(sr),.cam_clk(cam),.cam_rst(cr),.video_clk(vid),.video_rst(vr),
 .s_data(data),.s_valid(sv),.s_vsync(vs),.s_hsync(1'b0),.video_data(q),.video_valid(qv),.video_vsync(qs),.boundary_fault(fault));
wire [15:0] fq;wire fv,fvs;
cam_fir3 fir(.clk(vid),.rst(sr|fault),.in_valid(qv),.in_pixel(q),.in_vsync(qs),.out_valid(fv),.out_pixel(fq),.out_vsync(fvs));
wire abort_req;wire [1:0] req;
reg done=0,inject=0;
wire abort_all=fault|inject;
ddr_recovery #(.CAM_DATA_LEN(38400)) ddr(.axi_clk(vid),.axi_rst(sr),.transport_abort(abort_all),.dma_abort(1'b0),.dma_abort_req(abort_req),
 .dma_done(done),.axi_cam_en(1'b1),.cam_data_addr_1(32'h800000),.cam_data_addr_2(32'ha00000),.cam_data_len(17'd38400),
 .s_data(fq),.s_data_valid(fv),.s_hsync(1'b0),.s_vsync(fvs),.axi_data_ready(1'b0),.axi_cmd_ready(1'b0),.xdma_req(req),.xdma_ack(2'b11));
integer errors=0,ni=0,no=0,i,j,before_reset;
reg checking=1;
reg [15:0] expected[0:30000];
task check(input bit ok,input string msg);
 if(!ok) begin errors++;$display("FAIL %s t=%0t",msg,$time);end
endtask
always @(posedge cam) if(dut.wr_en) begin expected[ni]=data;ni++;end
always @(posedge vid) if(qv) begin
 if(checking) check(no<ni && q===expected[no],"pixel order/conservation");
 no++;
end
task tick(input bit valid,input bit level,input [15:0] value);
 @(negedge cam);sv=valid;vs=level;data=value;
endtask
task reset_all;
 cen=1;ven=1;sr=1;cr=1;vr=1;sv=0;vs=0;inject=0;done=0;
 repeat(30) @(negedge vid);
 ni=0;no=0;checking=1;
 cr=0;vr=0;repeat(4) @(negedge vid);sr=0;
 repeat(20) tick(0,0,0);
 tick(0,1,0);repeat(10) tick(0,1,0);repeat(20) tick(0,0,0);
 check(!fault,"reset and frame rearm");
endtask
task pixels(input integer n);
 for(i=0;i<n;i++) begin tick(1,0,i);tick(0,0,0);end
endtask
initial begin
 reset_all();ven=0;
 for(i=0;i<1000;i++) tick(1,0,i);
 tick(0,0,0);ven=1;
 for(i=1000;i<11000;i++) begin tick(1,0,i);tick(0,0,0);end
 repeat(2000) @(negedge vid);
 check(ni==11000 && no==11000 && !fault,"near-full wrap");
 $display("RECOVERY near_full accepted=%0d output=%0d fault=%b",ni,no,fault);
 for(j=0;j<8;j++) begin
  reset_all();pixels(64);repeat(200) @(negedge vid);
  check(no==64,"64 drained setup");
  if(j>=2) begin ven=0;pixels(128);end
  before_reset=no;checking=0;
  if(j==4) cen=0;
  #1;if(j%2==0) vr=1;else cr=1;
  if(j>=6) #100; else #0.2;
  vr=0;cr=0;
  #20;check(fault && !qv && abort_req,"short reset sticky/isolation/abort");
  cen=1;ven=1;pixels(32);repeat(100) @(negedge vid);
  check(no==before_reset && fault,"no old replay/no local restart");
  check(!ddr.ov5640_ddr_w_ctrl.publish && req==0,"no publish after reset");
  $display("RECOVERY unilateral case=%0d before=%0d after=%0d fault=%b",j,before_reset,no,fault);
 end
 reset_all();ven=0;
 for(i=0;i<1024;i++) tick(1,0,i);
 tick(0,0,0);tick(0,1,0);tick(0,1,0);
 check(dut.pixel_full && !fault,"marker accepted at pixel full");
 ven=1;repeat(2000) @(negedge vid);
 check(no==1024 && !fault,"full marker preserves ordering");
 $display("RECOVERY marker_full accepted=%0d output=%0d fault=%b",ni,no,fault);
 reset_all();ven=0;
 for(i=0;i<1030;i++) tick(1,0,i);
 tick(0,0,0);check(fault,"pixel overflow sticky");checking=0;before_reset=no;
 ven=1;pixels(64);repeat(100) @(negedge vid);
 check(no==before_reset && abort_req,"overflow fail closed");
 cr=1;vr=1;repeat(20) @(negedge vid);cr=0;vr=0;
 repeat(20) @(negedge vid);
 check(fault && abort_req,"joint local resets do not authorize DMA recovery");
 reset_all();pixels(64);repeat(200) @(negedge vid);
 check(no==64 && !fault,"explicit system reset recovery");
 $display("RECOVERY overflow_global_reset output=%0d fault=%b",no,fault);
 reset_all();ven=0;
 for(i=0;i<2050;i++) tick(0,i%2,0);
 check(fault && dut.transport_fault,"metadata-only overflow sticky");
 ven=1;repeat(20) @(negedge vid);
 check(abort_req && no==0,"metadata overflow abort/no pixels");
 $display("RECOVERY metadata_full fault=%b abort=%b",fault,abort_req);
 reset_all();tick(1,1,16'hdead);tick(0,1,0);
 check(fault,"illegal overlap sticky");
 repeat(20) @(negedge vid);
 check(no==0 && abort_req,"overlap never delivered");
 $display("RECOVERY overlap fault=%b abort=%b",fault,abort_req);
 // Clock absent through reset release: source must not enqueue until both
 // domains have clocked their release and exchanged ready acknowledgments.
 reset_all();sr=1;ven=0;cr=1;vr=1;
 repeat(10) tick(1,0,16'hbad0);
 cr=0;repeat(5) tick(1,0,16'hbad1);vr=0;sr=0;
 repeat(20) tick(1,0,16'hbad2);
 check(!dut.wr_en && !dut.video_ready_cam[1],"stopped reader blocks writes");
 sv=0;ni=0;no=0;ven=1;repeat(20) tick(0,1,0);
 check(!dut.armed,"high VSYNC at reset release not a fresh frame");
 repeat(10) tick(0,0,0);repeat(10) tick(0,1,0);tick(0,0,0);
 pixels(64);repeat(200) @(negedge vid);
 check(no==64 && ni==64 && !fault,"stopped reader release fresh-frame recovery");
 $display("RECOVERY stopped_release new_frame_output=%0d fault=%b",no,fault);
 // Controller fault injection: real wrapper + real derived controller.
 // Force state only to reach race cutpoints; dma_done is NOT a drain ack.
 for(j=0;j<5;j++) begin
  @(negedge vid);
  case(j)
   0:force ddr.ov5640_ddr_w_ctrl.curr_state=3'b010;
   1:force ddr.ov5640_ddr_w_ctrl.curr_state=3'b100;
   2:force ddr.ov5640_ddr_w_ctrl.curr_state=3'b011;
   3:force ddr.ov5640_ddr_w_ctrl.curr_state=3'b101;
   4:force ddr.ov5640_ddr_w_ctrl.curr_state=3'b110;
  endcase
  inject=1;done=1;#1;
  check(abort_req && !ddr.frame_good && !ddr.ov5640_ddr_w_ctrl.publish,"abort wins done/publish");
  @(posedge vid);#1;release ddr.ov5640_ddr_w_ctrl.curr_state;
  @(negedge vid);done=0;
  repeat(5) @(negedge vid);
  check(req==0 && !ddr.ov5640_ddr_w_ctrl.axi_cmd_valid,"no publish or new command");
  inject=0;
 end
 $display("RECOVERY controller_abort cutpoints=5 no_dma_retirement_claim=1");
 $display("RECOVERY_DONE errors=%0d",errors);
 if(errors) $fatal(1,"recovery failures");$finish;
end
initial begin #3000000;$fatal(1,"timeout");end
endmodule
