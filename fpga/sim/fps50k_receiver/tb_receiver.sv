`timescale 1ns/1ps
// Real splitter/CDC and complete camera wrappers; only IP FIFOs and DMA replaced.
module modeled_camera #(parameter ID=5, H=480, TAIL=256, TAG_TAIL=16)(
 input rxclk, clk, rst, vs, hs, de, input [15:0] pix,
 output [31:0] published, output integer admitted, dropped);
 localparam WORDS=640*H/8;
 localparam LW=$clog2(WORDS)+1;
 wire [31:0] ca,cl,state;
 wire cv,dv,dr; wire [127:0] data;
 reg done=0;
 wire abort_req;
 reg transaction=0, is_tag=0, waiting=0, vs_q=0;
 ov5640_ddr #(.DATA_WIDTH(16),.CAM_DATA_LEN(WORDS)) camera(
  .axi_clk(clk),.axi_rst(rst),.dma_done(done),.dma_abort(1'b0),.dma_abort_req(abort_req),
  .axi_cam_en(1'b1),.cam_data_addr_1(32'h100000),.cam_data_addr_2(32'h200000),
  .cam_data_len(LW'(WORDS)),.s_data(pix),.s_data_valid(de),.s_hsync(hs),.s_vsync(vs),
  .axi_data(data),.axi_data_valid(dv),.axi_data_ready(dr),
  .axi_cmd_addr(ca),.axi_cmd_len(cl),.axi_cmd_valid(cv),.axi_cmd_ready(!transaction),
  .xdma_ack(2'b11),.dbg_last_cnt(published),.dbg_state(state));
 integer words_left=0, countdown=0, source_pixels=0, accepted_pixels=0;
 integer cycle=0,last_pixel_cycle=0,last_beat_cycle=0,frame_id=0;
 assign dr=transaction&&!waiting;
 always @(posedge clk) begin
  cycle=cycle+1;
  done<=0;
  if(rst) begin
   transaction<=0;waiting<=0;vs_q<=0;admitted=0;dropped=0;frame_id=0;
   source_pixels=0;accepted_pixels=0;
  end else begin
   vs_q<=vs;
   if(vs&&!vs_q) begin
    if(frame_id>0 && source_pixels!=640*H) $fatal(1,"CAM%0d input pixels=%0d",ID,source_pixels);
    source_pixels=0;frame_id=frame_id+1;
   end
   if(de) source_pixels=source_pixels+1;
   if(camera.ov5640_ddr_w_en.s_vsync_rise) begin
    if(camera.m_vsync) begin admitted=admitted+1;accepted_pixels=0;end
    else dropped=dropped+1;
    $display("SOF CAM%0d frame=%0d cycle=%0d admitted=%0d dropped=%0d state=%0d flush=%0d complete=%0d last_pixel_age=%0d",ID,frame_id,cycle,admitted,dropped,state,camera.capture_flush,camera.capture_complete,cycle-last_pixel_cycle);
   end
   if(camera.m_data_valid) begin
    accepted_pixels=accepted_pixels+1;last_pixel_cycle=cycle;
   end
   if(abort_req||camera.capture_overflow) $fatal(1,"CAM%0d source fault",ID);
   if(cv&&!transaction) begin
    transaction<=1;is_tag<=cl==16;words_left=cl/16;
    if(cl!=16 && cl!=WORDS*16) $fatal(1,"invalid command length");
   end
   if(dv&&dr) begin
    if(!is_tag) begin
     // Validate every pixel of every admitted frame through the real packer.
     for(integer j=0;j<8;j=j+1)
      if(data[j*16+:16]!==16'((WORDS-words_left)*8+j))
       $fatal(1,"CAM%0d packed pixel mismatch beat=%0d lane=%0d got=%h",ID,WORDS-words_left,j,data[j*16+:16]);
    end else if(data[31:0]!=published+1) $fatal(1,"tag sequence mismatch");
    words_left=words_left-1;
    if(words_left==0) begin
     waiting<=1;countdown=is_tag?TAG_TAIL:TAIL;last_beat_cycle=cycle;
     if(!is_tag && accepted_pixels!=640*H) $fatal(1,"incomplete accepted frame");
    end
   end else if(waiting) begin
    if(countdown==0) begin
     done<=1;transaction<=0;waiting<=0;
     if(!is_tag && !camera.frame_good) $fatal(1,"frame_good false at data retirement");
     $display("DONE CAM%0d frame=%0d tag=%0d cycle=%0d last_pixel_age=%0d last_beat_age=%0d",ID,frame_id,is_tag,cycle,cycle-last_pixel_cycle,cycle-last_beat_cycle);
    end else countdown=countdown-1;
   end
  end
 end
endmodule

module tb_receiver;
 parameter H=480, FRAMES=6, BLANK=8, TAIL=256;
 reg rxclk=0,clk=0,rst=1,vs=0,hs=0,de=0;
 reg [15:0] pix=0;
 always #4 rxclk=~rxclk; // 125 MHz fabric
 always #2.5 clk=~clk; // 200 MHz AXI
 wire vs5,hs5,de5,vs6,hs6,de6;wire [15:0] pix5,pix6;
 sfp_rx_cam_if splitter(.i_rx_clk(rxclk),.i_rx_rst_n(!rst),.i_vs(vs),.i_hs(hs),.i_de(de),.i_pix(pix),
  .i_axi_clk(clk),.i_axi_rst_n(!rst),.o_vs5(vs5),.o_hs5(hs5),.o_de5(de5),.o_pix5(pix5),
  .o_vs6(vs6),.o_hs6(hs6),.o_de6(de6),.o_pix6(pix6));
 wire [31:0] pub5,pub6;wire integer a5,a6,d5,d6;
 modeled_camera #(.ID(5),.H(H),.TAIL(TAIL)) c5(rxclk,clk,rst,vs5,hs5,de5,pix5,pub5,a5,d5);
 modeled_camera #(.ID(6),.H(H),.TAIL(TAIL)) c6(rxclk,clk,rst,vs6,hs6,de6,pix6,pub6,a6,d6);
 integer exp5=-1,exp6=-1;
 real period_ns,fps;
 initial begin
  if($value$plusargs("EXP5=%d",exp5)) begin end
  if($value$plusargs("EXP6=%d",exp6)) begin end
  period_ns=(32.0+H*1280.0+(H-1)*3920.0+BLANK)*8.0;
  fps=1.0e9/period_ns;
  $display("CONFIG H=%0d FRAMES=%0d BLANK_RX=%0d blank_us=%0f TAIL_AXI=%0d tail_us=%0f period_ms=%0f offered_fps=%0f",H,FRAMES,BLANK,BLANK*0.008,TAIL,TAIL*0.005,period_ns/1e6,fps);
  repeat(20)@(negedge rxclk);rst=0;repeat(20)@(negedge rxclk);
  for(integer f=0;f<FRAMES;f=f+1) begin
   vs=1;repeat(8)@(negedge rxclk);vs=0;repeat(24)@(negedge rxclk);
   for(integer y=0;y<H;y=y+1) begin
    hs=1;de=1;
    for(integer x=0;x<1280;x=x+1) begin
     pix=16'(y*640+(x%640));@(negedge rxclk);
    end
    hs=0;de=0;
    if(y<H-1)repeat(3920)@(negedge rxclk);
   end
   repeat(BLANK)@(negedge rxclk);
  end
  repeat(TAIL+200)@(negedge rxclk);
  if(pub5!=a5||pub6!=a6||a5+d5!=FRAMES||a6+d6!=FRAMES) $fatal(1,"publication/admission accounting mismatch");
  if(exp5>=0 && pub5!=exp5) $fatal(1,"CAM5 expected %0d got %0d",exp5,pub5);
  if(exp6>=0 && pub6!=exp6) $fatal(1,"CAM6 expected %0d got %0d",exp6,pub6);
  $display("RESULT CAM5 admitted=%0d dropped=%0d published=%0d effective_fps=%0f CAM6 admitted=%0d dropped=%0d published=%0d effective_fps=%0f",a5,d5,pub5,fps*pub5/FRAMES,a6,d6,pub6,fps*pub6/FRAMES);
  $display("PASS receiver end-frame experiment");$finish;
 end
 initial begin #1000000000;$fatal(1,"timeout");end
endmodule
