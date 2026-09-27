`timescale 1ns/1ps
module tb_drm_gate;
reg clk=0, rst=1, ready=0;
always #5 clk=~clk;
GTP_GRS GRS_INST(.GRS_N(!rst));
reg inject=0;
reg [31:0] word_in=0;
wire [127:0] data_out;
wire valid_out;
integer nread=0, ndrm=0, blocked=0;
integer i;
reg old_mode;
ov5640_ddr_w dut(.axi_clk(clk), .axi_rst(rst), .data_len(19'd256),
 .s_data(24'd0), .s_data_valid(1'b0), .s_vsync(1'b0), .s_hsync(1'b0),
 .axi_data_last(), .dbg_axi_cnt(), .dbg_axi_num(), .dbg_zdin(), .dbg_zout(),
 .axi_data(data_out), .axi_data_valid(valid_out), .axi_data_ready(ready));
always @(posedge clk) if (!rst) begin
 if (dut.rd_en_drm) ndrm=ndrm+1;
 if (dut.almost_full_out) begin
   blocked=blocked+1;
   if (dut.rd_en_drm !== 0) $fatal(1,"Downstream backpressure violated");
 end
 if (dut.empty_drm && dut.rd_en_drm) $fatal(1,"Empty FIFO read");
 if (dut.fifo_we && dut.ov5640_ddr_fifo.full) $fatal(1,"Output overflow");
 if (valid_out && ready) begin
   for (integer lane=0; lane<4; lane=lane+1)
     if (data_out[lane*32+:32] !== (32'h12340000 + nread*4 + lane))
       $fatal(1,"Data mismatch beat=%0d lane=%0d got=%h",nread,lane,data_out);
   nread=nread+1;
 end
end
task push(input integer index);
 begin
 @(negedge clk); inject=1; word_in=32'h12340000+index;
 @(posedge clk); #1;
 if (dut.full) $fatal(1,"Unexpected DRM full");
 end
endtask
initial begin
 old_mode=$test$plusargs("OLD");
 force dut.wr_en=inject;
 force dut.din=word_in;
 force dut.almost_full_out=1'b1;
 repeat(8) @(negedge clk);
 rst=0;
 repeat(8) @(negedge clk);
 for(i=0;i<1023;i=i+1) push(i);
 @(negedge clk); inject=0;
 repeat(8) @(negedge clk);
 if(dut.almost_full_drm !== 1 || ndrm != 0) $fatal(1,"1023-word threshold not reached cleanly");
 $display("CHECK: 1023 write words, almost_full_drm=1, no reads under downstream backpressure");
 release dut.almost_full_out;
 if(old_mode) begin
   ready=1;
   repeat(64) @(negedge clk);
   if(ndrm != 0 || dut.almost_full_drm !== 1 || dut.empty_drm !== 0)
     $fatal(1,"Old deadlock not reproduced");
   $display("PASS_OLD: self-almost-full deadlock reproduced for 64 cycles");
   $finish;
 end
 repeat(64) @(negedge clk);
 if(ndrm == 0 || dut.almost_full_out !== 1 || dut.rd_en_drm !== 0)
   $fatal(1,"Recovery or real downstream stall failed");
 $display("CHECK: recovered while self almost-full; real output FIFO now applies backpressure, DRM reads=%0d",ndrm);
 ready=1;
 repeat(700) @(negedge clk);
 if(nread != 255 || dut.empty_drm !== 1) $fatal(1,"Expected 255 beats and three residual words, got %0d",nread);
 $display("CHECK: 1023 words drained to 255 complete beats plus 3 residual words");
 push(1023);
 @(negedge clk); inject=0;
 repeat(64) @(negedge clk);
 if(nread != 256 || ndrm != 256 || dut.empty_drm !== 1 || valid_out !== 0)
   $fatal(1,"Final drain failed reads=%0d outputs=%0d",ndrm,nread);
 $display("PASS_FIXED: 1024 words -> 256 ordered beats, both FIFOs empty; backpressure cycles=%0d",blocked);
 $finish;
end
initial begin #100000; $fatal(1,"Timeout"); end
endmodule
