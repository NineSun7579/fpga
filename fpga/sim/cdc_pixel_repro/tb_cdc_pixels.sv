`timescale 1ns/1ps
module tb_cdc_pixels;
parameter integer INJECT = 0;
parameter integer ROWS = 480;
parameter real CAM_HALF = 5.952380952;
parameter real CAM_PHASE = 0.0;
parameter integer REAL_ROWS = 0;
reg cam_clk=0, video_clk=0, rst=1;
initial begin #(CAM_PHASE); forever #(CAM_HALF) cam_clk=~cam_clk; end
always #3.809523810 video_clk=~video_clk;
reg [15:0] din=0;
reg valid=0, hs=0, vs=0;
wire [15:0] dout;
wire ov, oh, os;
ov5640_cdc #(.DATA_WIDTH(16)) dut(
 .cam_clk(cam_clk),.cam_rst(rst),.video_clk(video_clk),.video_rst(rst),
 .s_data(din),.s_valid(valid),.s_hsync(hs),.s_vsync(vs),
 .video_data(dout),.video_valid(ov),.video_hsync(oh),.video_vsync(os));
GTP_GRS GRS_INST(.GRS_N(1'b1));
integer ins=0, outs=0, errors=0, injections=0;
integer row, pixel;
reg [15:0] expected[0:307199];
always @(posedge cam_clk) if(!rst && valid) begin
 expected[ins]=din; ins=ins+1;
 if(dut.full) $fatal(1,"Unexpected full at input %0d",ins);
end
always @(posedge video_clk) if(!rst && ov) begin
 if(!INJECT && (outs>=ins || dout!==expected[outs])) begin
  if(errors<5) $display("Mismatch out=%0d in=%0d got=%h expected=%h",outs,ins,dout,expected[outs]);
  errors=errors+1;
 end
 outs=outs+1;
end
// Deliberately emulate one missed empty assertion AFTER a row has drained.
// This is a fault hypothesis, not a claim that zero-delay RTL has this fault.
task miss_empty;
 begin
  wait(dut.empty===1'b1);
  @(negedge video_clk);
  force dut.ov5640_cdc_fifo.U_ipm2l_fifo_ov5640_cdc_fifo.U_ipm2l_fifo_ctrl.asyn_rempty=1'b0;
  @(posedge video_clk); #0.1;
  release dut.ov5640_cdc_fifo.U_ipm2l_fifo_ov5640_cdc_fifo.U_ipm2l_fifo_ctrl.asyn_rempty;
  injections=injections+1;
 end
endtask
initial begin
 #100; @(negedge cam_clk); rst=0;
 repeat(10) @(negedge cam_clk);
 vs=1; repeat(10) @(negedge cam_clk); vs=0;
 for(row=0;row<ROWS;row=row+1) begin
  for(pixel=0;pixel<640;pixel=pixel+1) begin
   @(negedge cam_clk); hs=1; valid=1; din=(row*640+pixel)^16'h5a93;
   @(negedge cam_clk); valid=0;
  end
  @(negedge cam_clk); hs=0;
  // Leave enough row blanking to observe a complete erroneous pointer lap.
  if(REAL_ROWS) repeat(615) @(negedge cam_clk);
  else begin
   repeat(12) @(negedge video_clk);
   if(INJECT) miss_empty();
   repeat(2200) @(negedge video_clk);
  end
 end
 repeat(30) @(negedge video_clk);
 $display("RESULT INJECT=%0d input=%0d output=%0d excess=%0d injections=%0d errors=%0d",INJECT,ins,outs,outs-ins,injections,errors);
 if(errors || ins!=640*ROWS || outs!=640*ROWS+INJECT*2048*ROWS) $fatal(1,"Count/data failure");
 @(negedge cam_clk); vs=1;
 repeat(20) @(negedge video_clk);
 if(dut.dbg_cdc_input!==ins || dut.dbg_cdc_output!==outs || dut.dbg_cdc_drop!==0 || dut.dbg_cdc_seq!==2)
  $fatal(1,"Snapshot mismatch in=%0d out=%0d drop=%0d seq=%0d",dut.dbg_cdc_input,dut.dbg_cdc_output,dut.dbg_cdc_drop,dut.dbg_cdc_seq);
 $display("PASS stage snapshots input=%0d output=%0d dropped=%0d seq=%0d",dut.dbg_cdc_input,dut.dbg_cdc_output,dut.dbg_cdc_drop,dut.dbg_cdc_seq);
 $display("PASS CDC pixel conservation / injected pointer-lap signature");
 $finish;
end
initial begin #100000000; $fatal(1,"Timeout"); end
endmodule
