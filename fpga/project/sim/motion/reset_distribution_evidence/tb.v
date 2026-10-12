`timescale 1ns/1ps
module tb;
reg axi_clk=0;
always #5 axi_clk=~axi_clk;
reg sfp_motion_rst_n=1;
reg vs=0, de=0;
reg [15:0] pix=0;
wire [319:0] rec5, rec6;
(* ASYNC_REG = "TRUE", syn_preserve = 1, syn_keep = 1 *) reg [1:0] cam5_motion_reset_sync;
(* ASYNC_REG = "TRUE", syn_preserve = 1, syn_keep = 1 *) reg [1:0] cam6_motion_reset_sync;
wire cam5_motion_rst_n = cam5_motion_reset_sync[1];
wire cam6_motion_rst_n = cam6_motion_reset_sync[1];
always @(posedge axi_clk or negedge sfp_motion_rst_n) begin
    if (!sfp_motion_rst_n) cam5_motion_reset_sync <= 2'b00;
    else cam5_motion_reset_sync <= {cam5_motion_reset_sync[0], 1'b1};
end
always @(posedge axi_clk or negedge sfp_motion_rst_n) begin
    if (!sfp_motion_rst_n) cam6_motion_reset_sync <= 2'b00;
    else cam6_motion_reset_sync <= {cam6_motion_reset_sync[0], 1'b1};
end

motion_stream_adapter #(.WIDTH(4),.HEIGHT(4),.SAMPLE_STEP(1),
 .BLOCK_SAMPLES_X(2),.BLOCK_SAMPLES_Y(2)) a5
 (.clk(axi_clk),.rst_n(cam5_motion_rst_n),.vsync(vs),
 .pixel_valid(de),.pixel_rgb565(pix),.motion_record(rec5));
motion_stream_adapter #(.WIDTH(4),.HEIGHT(4),.SAMPLE_STEP(1),
 .BLOCK_SAMPLES_X(2),.BLOCK_SAMPLES_Y(2)) a6
 (.clk(axi_clk),.rst_n(cam6_motion_rst_n),.vsync(vs),
 .pixel_valid(de),.pixel_rgb565(pix),.motion_record(rec6));
task check_low;
begin
 if (cam5_motion_rst_n !== 0 || cam6_motion_rst_n !== 0)
  $fatal(1,"reset not asserted");
 if (rec5 !== 0 || rec6 !== 0) $fatal(1,"stale record survived reset");
end
endtask
task release_reset;
begin
 sfp_motion_rst_n=1;
 #1; check_low;
 @(posedge axi_clk); #1; check_low;
 @(posedge axi_clk); #1;
 if (cam5_motion_rst_n !== 1 || cam6_motion_rst_n !== 1)
  $fatal(1,"not released on second edge");
end
endtask
task frame;
integer i;
begin
 @(negedge axi_clk); vs=1;
 @(negedge axi_clk); vs=0;
 repeat(3) @(negedge axi_clk);
 for(i=0;i<16;i=i+1) begin de=1; @(negedge axi_clk); end
 de=0;
 repeat(10) @(negedge axi_clk);
end
endtask
initial begin
 #2; sfp_motion_rst_n=0; #1; check_low;
 #4; release_reset;
 frame; frame;
 if(rec5[32] !== 1 || rec6[32] !== 1) $fatal(1,"no valid comparison before loss");
 // Assert between edges, while a valid published record is visible.
 #2; sfp_motion_rst_n=0; #1; check_low;
 // Hold with source pixel activity; no acquisition through local reset.
 vs=1; de=1; repeat(3) @(negedge axi_clk); check_low;
 vs=0; de=0; #2; release_reset;
 repeat(3) @(negedge axi_clk); check_low_record;
 frame;
 if(rec5[32] !== 0 || rec6[32] !== 0) $fatal(1,"stale reference reused");
 frame;
 if(rec5[32] !== 1 || rec6[32] !== 1) $fatal(1,"comparison did not recover");
 // Sub-cycle loss must restart both release chains.
 #2; sfp_motion_rst_n=0; #1; check_low; release_reset;
 $display("PASS: extracted actual CAM5/6 chains; async assertion, second-edge release, stale record clearing, fresh reference and recovery");
 $finish;
end
task check_low_record;
begin if(rec5 !== 0 || rec6 !== 0) $fatal(1,"record changed without fresh VSYNC"); end
endtask
initial begin #10000; $fatal(1,"timeout"); end
endmodule
