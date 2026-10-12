`timescale 1ns/1ps
module tb_integration;
reg cam=0,video=0,rst=1,vs=0,href=0;
reg [7:0] data=0;
real cp=12.0,vp=10.0,ph=0.0;
reg clocks_enabled=0;
initial forever begin
 @(posedge clocks_enabled);
 while(clocks_enabled) begin #(cp/2.0); if(clocks_enabled) cam=~cam; end
end
initial forever begin
 @(posedge clocks_enabled); #(ph);
 while(clocks_enabled) begin #(vp/2.0); if(clocks_enabled) video=~video; end
end
GTP_GRS GRS_INST(.GRS_N(1'b1));
wire [15:0] pix,fpix; wire valid,hs,sv,fvalid,fvs;
wire [31:0] si,so,sd,seq;
frozen_capture_chain chain(.cam_pclk(cam),.cam_vsync(vs),.cam_href(href),.cam_data(data),
 .ov_rst_n(!rst),.cam_rst_n(!rst),.video_clk(video),.video_rst(rst),
 .video_data(pix),.video_valid(valid),.video_hsync(hs),.video_vsync(sv),
 .dbg_cdc_input(si),.dbg_cdc_output(so),.dbg_cdc_drop(sd),.dbg_cdc_seq(seq));
// Frozen parent MEDIAN_EN=0, KF_EN=0 are pure wire bypasses around this real FIR.
cam_fir3 fir(.clk(video),.rst(rst),.in_valid(valid),.in_pixel(pix),.in_vsync(sv),
 .out_valid(fvalid),.out_pixel(fpix),.out_vsync(fvs));
reg [16:0] length;
wire [127:0] axi_data; wire axi_valid,axi_last,cmd_valid,abort_req;
wire [31:0] cmd_len,reject,di,last_cnt;
wire [1:0] req;
reg done=0;
ov5640_ddr_tc04 #(.CAM_DATA_LEN(38400)) ddr(.axi_clk(video),.axi_rst(rst),
 .dma_abort(1'b0),.dma_abort_req(abort_req),.dma_done(done),.axi_cam_en(1'b1),
 .cam_data_addr_1(32'h800000),.cam_data_addr_2(32'ha00000),.cam_data_len(length),
 .s_data(fpix),.s_data_valid(fvalid),.s_hsync(hs),.s_vsync(fvs),
 .axi_data(axi_data),.axi_data_valid(axi_valid),.axi_data_last(axi_last),.axi_data_ready(1'b1),
 .axi_cmd_len(cmd_len),.axi_cmd_valid(cmd_valid),.axi_cmd_ready(1'b1),
 .xdma_req(req),.xdma_ack(2'b11),.dbg_reject_counts(reject),.dbg_input_pixels(di),.dbg_last_cnt(last_cnt));
integer bytes=0,src=0,outn=0,fn=0,accepted=0,beats=0,published=0;
integer remaining=0,delay_done=0,errors=0,cases=0,expected=0;
integer at_sof=0,start_lost=0,vs_lost=0,bad_lost=0;
integer sof_count=0,vidcycle=0,initial_sof_cycle=0,first_gap=-1;
reg trace_enabled=0;
integer trace_left=0;
reg svq=0;
time first_out,last_out,end_sof;
reg [15:0] queue[0:700000];
task check(input bit ok,input string message);
 if(!ok) begin $display("FAIL case=%0d %s t=%0t",cases,message,$time); errors=errors+1; end
endtask
always @(posedge cam) if(!rst) begin
 if(href) bytes=bytes+1;
 if(chain.cmos_frame_valid_r) begin queue[src]=chain.cmos_frame_data_r; src=src+1; end
end
always @(posedge video) begin
 if(rst) begin done<=0;remaining=0;delay_done=0;svq=0;end
 else begin
  done<=0;
  if($test$plusargs("SMOKE")&&ddr.raw_sof)
   $display("ADMISSION case=%0d src=%0d engine_busy=%0b capture_flush=%0b capture_complete=%0b published=%0d",cases,src,ddr.engine_busy,ddr.capture_flush,ddr.capture_complete,published);
  if(trace_enabled&&outn>=expected-4&&trace_left>0) begin
   $display("BOUNDARY t=%0t src=%0d out_before=%0d cdc_valid=%0b fifo_empty=%0b cdc_vs=%0b fir_valid=%0b fir_vs=%0b raw_sof=%0b admitted=%0b pixel_count=%0d",$time,src,outn,valid,chain.ov5640_cdc.empty,sv,fvalid,fvs,ddr.raw_sof,ddr.m_data_valid,ddr.pixel_count);
   trace_left=trace_left-1;
  end
  if(cmd_valid) remaining=cmd_len/16;
  if(axi_valid) begin
   check(remaining>0,"AXI data without command credit");
   check((^axi_data)!==1'bx,"unknown vendor FIFO payload");
   remaining=remaining-1;
   if(ddr.frame_active) beats=beats+1;
   if(remaining==0) delay_done=4;
  end
  if(delay_done>0) begin
   delay_done=delay_done-1;
   if(delay_done==0) done<=1;
  end
  if(ddr.ov5640_ddr_w_ctrl.publish) published=published+1;
  vidcycle=vidcycle+1;
  if(sv&&!svq) begin
   if(sof_count==0) initial_sof_cycle=vidcycle;
   sof_count=sof_count+1;at_sof=outn;end_sof=$time;
  end
  svq=sv;
  if(valid) begin
   check(outn<src,"FIFO output without input");
   check(pix===queue[outn],"vendor CDC FIFO data/order mismatch");
   if(outn==0) begin first_out=$time;if(sof_count>0) first_gap=vidcycle-initial_sof_cycle;end
   outn=outn+1;last_out=$time;
  end
  if(fvalid) begin
   fn=fn+1;
   if(!ddr.m_data_valid&&!ddr.capture_complete) begin
    if(fvs) vs_lost=vs_lost+1;
    else if(ddr.capture_bad) bad_lost=bad_lost+1;
    else start_lost=start_lost+1;
   end
  end
  if(ddr.m_data_valid) accepted=accepted+1;
 end
end
task tick(input bit v,input bit h,input [7:0] d);
 @(negedge cam); #0.001; vs=v;href=h;data=d;
endtask
task idle(input integer n); repeat(n) tick(0,0,0);endtask
task marker(input integer n);repeat(n) tick(1,0,0);endtask
task scenario(input integer w,h,hblank,tail,head,pulse,input real cam_period,video_period,phase,input bit must_good);
 integer x,y,k;
 begin
  clocks_enabled=0;rst=1;vs=0;href=0;
  #1000;cam=0;video=0;cp=cam_period;vp=video_period;ph=phase;clocks_enabled=1;
  repeat(30) @(negedge video);
  #0.001; rst=0;
  bytes=0;src=0;outn=0;fn=0;accepted=0;beats=0;published=0;
  at_sof=0;start_lost=0;vs_lost=0;bad_lost=0;first_out=0;last_out=0;end_sof=0;
  sof_count=0;vidcycle=0;initial_sof_cycle=0;first_gap=-1;
  expected=w*h;length=expected/8;cases=cases+1;
  trace_enabled=(w==640&&video_period==16.0&&tail==1);trace_left=14;
  // Actual WAIT_FRAME=10: ten suppressed markers, then the admitted eleventh.
  repeat(10) begin marker(16);idle(32);end
  marker(pulse);idle(head);
  for(y=0;y<h;y=y+1) begin
   for(x=0;x<w*2;x=x+1) tick(0,1,(y*w*2+x)&255);
   if(y<h-1) idle(hblank);
  end
  idle(tail);marker(16);idle(32);
  repeat(1500) @(negedge video);
  check(bytes==expected*2,"input byte total");
  check(src==expected,"capture valid total");
  check(outn==expected,"FIFO total conservation");
  check(fn==expected,"FIR total conservation");
  check(si==expected,"source snapshot");
  check(sd==0,"source FIFO drops");
  check(reject[31:16]==0,"DDR overflow");
  if(must_good) begin
   check(accepted==expected,"normal admission count");
   check(published==1,"normal publish");
   check(reject[15:0]==0,"normal no short");
   check(so==expected&&di==expected,"normal output windows");
  end
  $display("RESULT case=%0d w=%0d h=%0d hb=%0d tail=%0d head=%0d pulse=%0d cp=%0.3f vp=%0.3f phase=%0.3f bytes=%0d source=%0d snap=%0d drop=%0d output=%0d window=%0d ddrwin=%0d accepted=%0d beats=%0d publish=%0d short=%0d at_sof=%0d startlost=%0d vslost=%0d badlost=%0d tail_delta_ns=%0d normal=%0d sof_count=%0d first_gap=%0d",cases,w,h,hblank,tail,head,pulse,cp,vp,phase,bytes,src,si,sd,outn,so,di,accepted,beats,published,reject[15:0],at_sof,start_lost,vs_lost,bad_lost,$signed(end_sof)-$signed(last_out),must_good,sof_count,first_gap);
 end
endtask
integer p,b,f,k,x,window_sum,source_sum;
real periods[0:5];
initial begin
 if($test$plusargs("SMOKE")||$test$plusargs("REPRO")) begin
  if($test$plusargs("SMOKE")) begin
   scenario(32,4,64,0,32,16,12.0,10.0,0.0,0);
   check(accepted==127&&published==0&&reject[15:0]==1,"minimal small reproduction");
   scenario(32,4,64,1,32,16,12.0,10.0,0.0,1);
   // Continue two normal frames without resetting capture, FIFOs or DDR.
   for(k=0;k<2;k=k+1) begin
    for(p=0;p<4;p=p+1) begin
     for(x=0;x<64;x=x+1) tick(0,1,(p*64+x)&255);
     if(p<3) idle(64);
    end
    idle(128);marker(16);idle(64);repeat(100) @(negedge video);
    check(si==128&&so==128&&di==128&&sd==0,"continuous normal snapshots");
   end
   // A one-PCLK tail saves the last pixel but the next SOF still arrives
   // before frame/tag retirement. The busy gate intentionally skips frame 2.
   check(src==384&&outn==384&&accepted==256&&published==2&&reject==0,"busy marker skips complete next frame");
   $display("EXPECTED_BUSY_SKIP frames=3 source=%0d output=%0d accepted=%0d published=%0d shorts=%0d",src,outn,accepted,published,reject[15:0]);
   scenario(32,4,64,128,32,16,12.0,10.0,0.0,1);
   for(k=0;k<2;k=k+1) begin
    for(p=0;p<4;p=p+1) begin
     for(x=0;x<64;x=x+1) tick(0,1,(p*64+x)&255);
     if(p<3) idle(64);
    end
    idle(128);marker(16);idle(64);repeat(100) @(negedge video);
    check(si==128&&so==128&&di==128&&sd==0,"continuous generous-blank snapshots");
   end
   check(src==384&&outn==384&&accepted==384&&published==3&&reject==0,"continuous normal publication");
   $display("CONTINUOUS frames=3 source=%0d output=%0d accepted=%0d published=%0d shorts=%0d",src,outn,accepted,published,reject[15:0]);
  end else begin
   scenario(640,480,616,1,32,16,12.0,16.0,0.0,0);
   check(accepted==307199&&published==0&&reject[15:0]==1,"full-size positive-blank reproduction");
   scenario(640,480,616,3,32,16,12.0,16.0,0.0,1);
  end
  $display("INTEGRATION_DONE cases=%0d errors=%0d",cases,errors);
  if(errors) $fatal(1,"integration failures");
  $finish;
 end
 periods[0]=5.0;periods[1]=10.0;periods[2]=16.0;
 periods[3]=23.0;periods[4]=24.0;periods[5]=30.0;
 scenario(32,4,16,64,16,16,12.0,10.0,0.1,1);
 // Normal generous blank: including video slower than peak source rate,
 // but sustainable with the line blank and no FIFO overflow.
 for(f=0;f<6;f=f+1) for(p=0;p<4;p=p+1)
  scenario(32,4,64,128,32,16,12.0,periods[f],p*2.1,1);
 // Non-overlapping raw HREF/VSYNC, compressed trailing blank sensitivity.
 for(f=0;f<6;f=f+1) for(p=0;p<4;p=p+1) for(b=0;b<=12;b=b+1)
  scenario(32,4,64,b,32,16,12.0,periods[f],p*2.1,0);
 for(p=0;p<4;p=p+1) for(b=13;b<=26;b=b+1)
  scenario(32,4,64,b,32,16,12.0,30.0,p*2.1,0);
 // Startup admission: narrow raw marker and zero to four post-marker clocks.
 for(f=0;f<6;f=f+1) for(p=0;p<4;p=p+1) for(b=0;b<=4;b=b+1)
  scenario(32,4,64,128,b,1,12.0,periods[f],p*2.1,0);
 for(f=0;f<6;f=f+1) for(p=0;p<4;p=p+1) for(b=0;b<=4;b=b+1)
  scenario(32,4,64,128,b,3,12.0,periods[f],p*2.1,1);
 // Full VGA controls at representative 84/64 MHz camera periods.
 scenario(640,480,616,2000,616,64,11.905,10.0,0.1,1);
 scenario(640,480,616,2000,616,64,15.625,10.0,3.7,1);
 scenario(640,480,616,2000,616,64,12.0,30.0,2.1,1);
 // Full-size compressed boundary reproductions, no raw VSYNC/HREF overlap.
 for(b=0;b<=6;b=b+1) scenario(640,480,616,b,32,16,12.0,10.0,0.0,0);
 scenario(640,480,616,1,32,16,12.0,30.0,2.1,0);
 scenario(640,480,616,2000,0,1,12.0,30.0,2.1,0);
 scenario(640,480,616,1,32,16,12.0,16.0,0.0,0);
 check(accepted==307199&&published==0&&reject[15:0]==1,"full-size positive-blank reproduction");
 scenario(640,480,616,3,32,16,12.0,16.0,0.0,1);
 scenario(640,480,616,504*1896,616,64,11.905,10.0,4.2,1);
 // Consecutive frame-window conservation: initial deficit, following complete
 // windows, then empty flush interval catches the last displaced tail pixel.
 scenario(32,4,64,0,32,16,12.0,10.0,0.0,0);
 check(so==127&&si==128,"conservation seed");
 window_sum=so;source_sum=si;
 for(k=0;k<2;k=k+1) begin
  for(p=0;p<4;p=p+1) begin
   for(x=0;x<64;x=x+1) tick(0,1,(p*64+x)&255);
   if(p<3) idle(64);
  end
  marker(16);idle(64);repeat(100) @(negedge video);
  window_sum=window_sum+so;source_sum=source_sum+si;
  $display("CONSERVE interval=%0d source=%0d window=%0d total_in=%0d total_out=%0d",k+2,si,so,src,outn);
 end
 marker(16);idle(64);repeat(100) @(negedge video);
 window_sum=window_sum+so;source_sum=source_sum+si;
 $display("CONSERVE flush source=%0d window=%0d sum_source=%0d sum_output=%0d",si,so,source_sum,window_sum);
 check(source_sum==384&&window_sum==384&&outn==384,"consecutive window conservation");
 $display("INTEGRATION_DONE cases=%0d errors=%0d",cases,errors);
 if(errors) $fatal(1,"integration failures");
 $finish;
end
endmodule
