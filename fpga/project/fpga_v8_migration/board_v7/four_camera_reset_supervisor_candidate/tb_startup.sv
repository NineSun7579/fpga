`timescale 1ns/1ps
module tb_startup;
reg clk50=0,video=0;
always #10 clk50=~clk50;
always #3.81 video=~video;
reg axi_rst=1, cold=1;
wire ctrl,cam_rst_n;
review_startup startup(clk50,ctrl,cam_rst_n);
wire [3:0] bad_fault,good_fault;
reg epoch=1,request=0;
wire supervisor_cold,session_fault,admit;wire [3:0] started,scam;
four_camera_reset_supervisor supervisor(.clk(video),.epoch_reset(epoch),.cold_request(request),
 .source_clk(scam),.i2c_start_en({4{cam_rst_n}}),.cam_init_done({4{cam_rst_n}}),.ov_rst_n({4{cam_rst_n}}),
 .video_reset(axi_rst),.boundary_fault(good_fault),.capture_abort_req(4'd0),.writer_abort(4'd0),
 .cold_system_reset(supervisor_cold),.camera_session_fault(session_fault),.admission_enable(admit),.source_started(started));
GTP_GRS GRS_INST(.GRS_N(1'b1));
genvar i;
generate for(i=0;i<4;i=i+1) begin: cameras
  reg cam=0;
  always #(5.9525+i*0.03) cam=~cam;
  cdc_recovery bad(.system_reset(axi_rst),.cam_clk(cam),.cam_rst(!cam_rst_n),
    .video_clk(video),.video_rst(axi_rst),.s_data(16'b0),.s_valid(1'b0),.s_hsync(1'b0),.s_vsync(1'b0),.boundary_fault(bad_fault[i]));
  assign scam[i]=cam;
  cdc_recovery good(.system_reset(supervisor_cold),.cam_clk(cam),.cam_rst(!cam_rst_n),
    .video_clk(video),.video_rst(axi_rst),.s_data(16'b0),.s_valid(1'b0),.s_hsync(1'b0),.s_vsync(1'b0),.boundary_fault(good_fault[i]));
end endgenerate
integer errors=0;
initial begin
  #100;epoch=0;request=1;#900; axi_rst=0;
  wait(cam_rst_n===1); repeat(20) @(negedge video);
  if(bad_fault!==4'b1111) begin $display("FAIL startup counterexample missing"); errors++; end
  // Cold initialization stays authorized through normal local reset release.
  cold=0; repeat(100) @(negedge video);
  if(!admit || session_fault) begin $display("FAIL supervised actual startup");errors++;end
  if(good_fault!==0) begin $display("FAIL cold ordering"); errors++; end
  $display("REVIEW_STARTUP actual_50MHz_time_ns=%0.3f naive_fault=%b ordered_fault=%b errors=%0d",$realtime,bad_fault,good_fault,errors);
  axi_rst=1;repeat(10) @(negedge video);axi_rst=0;repeat(10) @(negedge video);
  if(!session_fault || supervisor_cold || admit) begin $display("FAIL warm reset reauthorized");errors++;end
  $display("SUPERVISED_ACTUAL_STARTUP warm_fault=%b cold=%b errors=%0d",session_fault,supervisor_cold,errors);
  $finish;
end
initial begin #10000000; $display("FAIL startup timeout"); $finish; end
endmodule
