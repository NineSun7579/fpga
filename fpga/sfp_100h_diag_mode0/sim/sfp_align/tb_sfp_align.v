`timescale 1ns/1ps
module tb_sfp_align;
 reg free_clk=0;
 always #20 free_clk=~free_clk;
 wire clk, rst_n, en, vs, hs, de, overflow;
 wire [31:0] rxd;
 wire [3:0] rxk;
 wire [15:0] pix;
 sfp_rx_link dut (
  .i_free_clk(free_clk), .i_refckp(1'b0), .i_refckn(1'b0),
  .i_l2rxn(1'b0), .i_l2rxp(1'b0),
  .o_l2txn(), .o_l2txp(), .o_sfp_tx_disable(), .o_pll_lock(),
  .o_txlane_done(), .o_rxlane_done(), .o_pcs_synced(), .o_rx_sigdet(),
  .o_rx_clk(clk), .o_rx_rst_n(rst_n), .o_rx_en(en), .o_rxd(rxd), .o_rxk(rxk)
 );
 sfp_video_rx decoder (.i_clk(clk), .i_rst_n(rst_n), .i_en(en),
  .i_rxd(rxd), .i_rxk(rxk), .o_vs(vs), .o_hs(hs), .o_de(de),
  .o_pix(pix), .o_overflow(overflow));
 integer input_file, output_file, trace_file, rc, count=0, frame_pixels=0;
 integer sof=0, controls=0, overflows=0, relocks=0;
 reg prev_vs=0;
 reg [1:0] prev_rot=0;
 reg [31:0] word_d;
 reg [3:0] word_k;
 reg [1023:0] vector_path, pixel_path, trace_path;
 always @(posedge clk) begin
  if (rst_n && en) begin
   if (rxk==4'b1001) controls=controls+1;
   if (dut.rot!=prev_rot) relocks=relocks+1;
   prev_rot=dut.rot;
   if ((dut.hit0|dut.hit1|dut.hit2|dut.hit3) &&
       ((dut.hit0 && dut.rot!=0) || (dut.hit1 && dut.rot!=1) ||
        (dut.hit2 && dut.rot!=2) || (dut.hit3 && dut.rot!=3)))
    $fdisplay(trace_file,"t=%0t old_rot=%0d hit=%b%b%b%b old_output=%08h/%h candidates=%08h/%h %08h/%h %08h/%h %08h/%h",
      $time,dut.rot,dut.hit3,dut.hit2,dut.hit1,dut.hit0,rxd,rxk,
      dut.cand_d0,dut.cand_k0,dut.cand_d1,dut.cand_k1,
      dut.cand_d2,dut.cand_k2,dut.cand_d3,dut.cand_k3);
  end
  #1;
  if (rst_n) begin
   if (overflow) overflows=overflows+1;
   if (vs && !prev_vs) sof=sof+1;
   prev_vs=vs;
   if (de) begin
    count=count+1;
    if (sof>0) frame_pixels=frame_pixels+1;
    $fdisplay(output_file,"%04h",pix);
   end
  end
 end
 initial begin
  if (!$value$plusargs("VECTOR=%s",vector_path)) $fatal(1,"VECTOR required");
  if (!$value$plusargs("PIXELS=%s",pixel_path)) $fatal(1,"PIXELS required");
  if (!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"TRACE required");
  input_file=$fopen(vector_path,"r");
  output_file=$fopen(pixel_path,"w");
  trace_file=$fopen(trace_path,"w");
  if (!input_file || !output_file || !trace_file) $fatal(1,"file open failed");
  // Accelerate only the power-on counter. Production alignment RTL is untouched.
  dut.por_cnt=18'd249999;
  repeat(12) @(negedge clk);
  dut.u_hsst.lane_done=1;
  while (!$feof(input_file)) begin
   rc=$fscanf(input_file,"%h %h\n",word_d,word_k);
   if (rc==2) begin
    @(negedge clk);
    dut.u_hsst.drive_d=word_d;
    dut.u_hsst.drive_k=word_k;
   end
  end
  // The vectors end with a long blanking tail to drain the pixel FIFO.
  repeat(16) @(negedge clk);
  $display("RESULT pixels=%0d frame_pixels=%0d sof=%0d controls=%0d relocks=%0d overflow=%0d",count,frame_pixels,sof,controls,relocks,overflows);
  $fclose(input_file); $fclose(output_file); $fclose(trace_file);
  $finish;
 end
endmodule
