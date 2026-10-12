`timescale 1ns/1ps
module tb_cam5_idle_recovery;
 wire [15:0] available;
`ifdef VENDOR_FIFO
 localparam WORDS=2048;
 GTP_GRS GRS_INST(.GRS_N(1'b1));
`else
 localparam WORDS=64;
`endif
 localparam PIXELS=WORDS*8, BANK0=32'h10000, BANK1=32'h20000;
 localparam LEN_WIDTH=$clog2(WORDS)+1;
 reg clk=0;always #5 clk=~clk;
 reg auto_ack=1;
 reg rst=1,sv=0,pv=0;reg [15:0] pixel=0;
 wire [31:0] ca,cl,awaddr,last_cnt,state,prev_base;
 wire cv,cr,dv,dr,done,aborted,abort_req,av,ar,wv,wr,wl,br;
 wire [127:0] data,wd;wire [15:0] ws;wire [7:0] al;
 wire [1:0] req;reg [1:0] ack=0;
 ov5640_ddr #(.DATA_WIDTH(16),.CAM_DATA_LEN(WORDS)) camera(
  .axi_clk(clk),.axi_rst(rst),.dma_done(done),.dma_abort(aborted),.dma_abort_req(abort_req),.axi_data_available(available),
  .axi_cam_en(1'b1),.cam_data_addr_1(BANK0),.cam_data_addr_2(BANK1),.cam_data_len(LEN_WIDTH'(WORDS)),
  .s_data(pixel),.s_data_valid(pv),.s_hsync(1'b1),.s_vsync(sv),
  .axi_data(data),.axi_data_valid(dv),.axi_data_ready(dr),.axi_data_last(),
  .axi_cmd_addr(ca),.axi_cmd_len(cl),.axi_cmd_valid(cv),.axi_cmd_ready(cr),
  .xdma_req(req),.xdma_ack(ack),.dbg_last_cnt(last_cnt),.dbg_state(state),.prev_frame_base(prev_base),
  .dbg_axi_cnt(),.dbg_axi_num(),.dbg_zdin(),.dbg_zout(),.dbg_wd_cnt());
 reg stall_aw=0,stall_w=0,stall_b=0,tag_error=0,data_error=0;
 reg bv=0;reg [1:0] resp=0;
 axi_dma_write #(.BURST_LEN(16),.WAIT_FOR_DATA(1),.WD_LIMIT(64)) dma(
  .clk(clk),.rst(rst),.abort_req(abort_req),.data_in_abort(aborted),
  .cmd_addr(ca),.cmd_len(cl),.cmd_valid(cv),.cmd_ready(cr),.cmd_id(4'd1),
  .data_in_available(available),.data_in(data),.data_in_keep(16'hffff),.data_in_valid(dv),.data_in_ready(dr),.data_in_last(done),
  .m_axi_awaddr(awaddr),.m_axi_awlen(al),.m_axi_awvalid(av),.m_axi_awready(ar),
  .m_axi_awid(),.m_axi_awsize(),.m_axi_awburst(),.m_axi_awlock(),.m_axi_awcache(),.m_axi_awprot(),
  .m_axi_wdata(wd),.m_axi_wstrb(ws),.m_axi_wlast(wl),.m_axi_wvalid(wv),.m_axi_wready(wr),
  .m_axi_bvalid(bv&&!stall_b),.m_axi_bready(br),.m_axi_bresp(resp),.m_axi_bid(4'd1));
 integer cycle=0,left=0,bdelay=0,offset=0,aw_count=0,b_count=0,abort_count=0,tag_count=0;
 integer success_count=0,zero_strobes=0;
 reg bus_active=0,cur_tag=0;
 reg [7:0] mem[0:196607];
 assign ar=!stall_aw&&!bus_active&&!bv&&(cycle%5!=0);
 assign wr=!stall_w&&bus_active&&(cycle%7!=0);
 reg aw_held=0,w_held=0;reg [39:0] aw_saved;reg [144:0] w_saved;
 integer j;
 always @(posedge clk)begin
  cycle<=cycle+1;
  if(!rst)begin
   if(aw_held&&(!av||{awaddr,al}!==aw_saved))$fatal(1,"AW unstable under backpressure");
   if(w_held&&(!wv||{wd,ws,wl}!==w_saved))$fatal(1,"W unstable under backpressure");
   aw_held<=av&&!ar;aw_saved<={awaddr,al};
   w_held<=wv&&!wr;w_saved<={wd,ws,wl};
   if(done&&aborted)$fatal(1,"success and abort overlap");
   if(camera.capture_flush&&(dma.trans||av||wv||bus_active||bv))$fatal(1,"local flush before AXI retirement");
   if(av&&ar)begin
    if(bus_active||bv)$fatal(1,"multiple outstanding bursts");
    aw_count=aw_count+1;left=al+1;offset=awaddr;bus_active<=1;
    cur_tag=(awaddr==BANK0+WORDS*16)||(awaddr==BANK1+WORDS*16);
    if(cur_tag)tag_count=tag_count+1;
   end
   if(wv&&wr)begin
    if(!bus_active||left==0)$fatal(1,"W without AW obligation");
    if(wl!==(left==1))$fatal(1,"WLAST mismatch");
    if(ws==0)zero_strobes=zero_strobes+1;
    for(j=0;j<16;j=j+1)if(ws[j])mem[offset+j]=wd[j*8+:8];
    offset=offset+16;left=left-1;
    if(left==0)begin bdelay=4;resp<=((cur_tag&&tag_error)||(!cur_tag&&data_error))?2'b10:0;end
   end
   if(bdelay>0)begin bdelay=bdelay-1;if(bdelay==0)bv<=1;end
   if(bv&&!stall_b&&br)begin bv<=0;bus_active<=0;b_count=b_count+1;end
   if(aborted)begin abort_count=abort_count+1;$display("ABORT t=%0t state=%0d pixels=%0d",$time,state,camera.pixel_count);end
  end
 end
 task automatic sof;
 begin @(negedge clk);sv=1;repeat(6)@(negedge clk);sv=0;repeat(6)@(negedge clk);end
 endtask
 task automatic pixels(input integer seed,input integer n);
 integer i;
 begin
  for(i=0;i<n;i=i+1)begin pixel=seed+i;pv=1;@(negedge clk);end
  pv=0;
 end endtask
 task automatic send_frame(input integer seed,input integer n);
 begin sof();pixels(seed,n);end endtask
 task automatic idle;
 begin wait(!camera.engine_busy&&!camera.capture_flush);repeat(8)@(negedge clk);end endtask
 task automatic check_frame(input integer seed,input integer bank,input integer seq);
 integer i;reg [15:0] actual;
 begin
  wait(last_cnt==seq);idle();
  for(i=0;i<PIXELS;i=i+1)begin
   actual={mem[bank+i*2+1],mem[bank+i*2]};
   if(actual!==(16'(seed+i)))$fatal(1,"pixel alignment bank=%h index=%0d got=%h expected=%h",bank,i,actual,16'(seed+i));
  end
  if({mem[bank+WORDS*16+3],mem[bank+WORDS*16+2],mem[bank+WORDS*16+1],mem[bank+WORDS*16]}!==seq)$fatal(1,"tag mismatch");
  if(prev_base!==bank||req==0)$fatal(1,"bank/request not published after tag");
  success_count=success_count+1;
  $display("PASS complete frame seq=%0d all %0d pixels including (0,0), bank=%h",seq,PIXELS,bank);
  if(auto_ack)begin ack=3;repeat(2)@(negedge clk);ack=0;end
 end endtask
 task automatic failed_frame(input integer before_abort,input integer before_tags,input integer before_success);
 begin
  wait(abort_count==before_abort+1);idle();
  if(tag_count!=before_tags||last_cnt!=before_success||req!=0)$fatal(1,"bad frame published tag/request/success");
  if(camera.ov5640_ddr_w.cnt!=0||camera.w_valid||camera.ov5640_ddr_w.wr_en_drm)$fatal(1,"capture pipeline not empty after flush");
 end endtask
 integer a,t,s;
 initial begin
  for(j=0;j<196608;j=j+1)mem[j]=8'hcc;
  repeat(6)@(negedge clk);rst=0;idle();
  send_frame('h1000,PIXELS);check_frame('h1000,BANK0,1);
  // Short frame leaves odd pixel and partial 128-bit FIFO group behind.
  a=abort_count;t=tag_count;s=last_cnt;
  send_frame('h2000,13);sof();failed_frame(a,t,s);
  $display("PASS short frame at next SOF aborts, no tag/req/counter; packer/FIFOs flushed");
  send_frame('h3000,PIXELS);check_frame('h3000,BANK1,2);
  a=abort_count;t=tag_count;s=last_cnt;
  send_frame('h4000,11);repeat(20)@(negedge clk);if(av||bus_active)$fatal(1,"partial pre-AW source reserved DDR");failed_frame(a,t,s);
  $display("PASS missing data watchdog abort without another SOF");
  send_frame('h5000,PIXELS);check_frame('h5000,BANK0,3);
  // AW offered then source abort: AW must survive until actually accepted.
  a=abort_count;t=tag_count;s=last_cnt;stall_aw=1;
  send_frame('h6000,129);repeat(10)@(negedge clk);sof();repeat(30)@(negedge clk);
  if(!av||!abort_req||abort_count!=a||camera.capture_flush)$fatal(1,"cancelled outstanding AW");
  stall_aw=0;failed_frame(a,t,s);
  $display("PASS abort during AW stall retains AW and drains accepted burst");
  send_frame('h7000,PIXELS);check_frame('h7000,BANK1,4);
  // Natural overflow in reduced-capacity FIFO model with W stalled.
  a=abort_count;t=tag_count;s=last_cnt;stall_w=1;
  send_frame('h8000,PIXELS);repeat(20)@(negedge clk);
  if(!abort_req||abort_count!=a||camera.capture_flush)$fatal(1,"overflow not sticky or flushed while W stalled");
  stall_b=1;stall_w=0;wait(bv);repeat(20)@(negedge clk);
  if(abort_count!=a||camera.capture_flush)$fatal(1,"flushed before real B response");
  stall_b=0;failed_frame(a,t,s);
  $display("PASS FIFO overflow + W/B backpressure; no premature flush/publication");
  send_frame('h9000,PIXELS);check_frame('h9000,BANK0,5);
  // Slave error on payload retires command as abort, unissued tail discarded.
  a=abort_count;t=tag_count;s=last_cnt;data_error=1;
  send_frame('ha000,PIXELS);failed_frame(a,t,s);data_error=0;
  $display("PASS payload BRESP error prevents tag");
  send_frame('hb000,PIXELS);check_frame('hb000,BANK1,6);
  // Tag bus failure must not advance success accounting or switch write bank.
  a=abort_count;t=tag_count;s=last_cnt;tag_error=1;
  send_frame('hc000,PIXELS);wait(abort_count==a+1);idle();tag_error=0;
  if(last_cnt!=s||req!=0||tag_count!=t+1||camera.w_ping_o!=0)$fatal(1,"tag error published success");
  $display("PASS tag BRESP error does not publish req/count/bank");
  send_frame('hd000,PIXELS);check_frame('hd000,BANK0,7);
  // Retain both pending requests, overwrite only the selected bank, then fail.
  auto_ack=0;
  send_frame('he000,PIXELS);check_frame('he000,BANK1,8);
  send_frame('hf000,PIXELS);check_frame('hf000,BANK0,9);
  if(req!=3)$fatal(1,"expected two retained valid bank requests");
  a=abort_count;t=tag_count;
  send_frame('h1800,13);sof();wait(abort_count==a+1);idle();
  if(req!=1||last_cnt!=9||prev_base!=BANK0||tag_count!=t)$fatal(1,"dirty target bank still valid or previous good bank lost");
  $display("PASS dirty bank request invalidated; last good bank remains valid after abort");
  // No publication until the tag's actual B response, even after all W data.
  auto_ack=1;
  send_frame('h2800,PIXELS);wait(cur_tag);@(negedge clk);stall_b=1;
  wait(bv);repeat(100)@(negedge clk);
  if(last_cnt!=9||req!=1||prev_base!=BANK0||aborted)$fatal(1,"published tag before successful B");
  stall_b=0;check_frame('h2800,BANK1,10);
  $display("PASS tag B backpressure longer than WD_LIMIT never publishes early");
     // Reproduce the observed idle + zero-fault + complete capture trap.
   idle();
   @(negedge clk);
   camera.capture_open = 1;
   camera.capture_bad = 0;
   camera.pixel_count = PIXELS;
   camera.pixel_limit = PIXELS;
   repeat(24) @(negedge clk);
   if(camera.capture_stop || camera.capture_open)
     $fatal(1,"idle complete capture remains permanently closed");
   if(last_cnt!=10 || state!=1 || cv || av || bus_active)
     $fatal(1,"orphan recovery fabricated completion or AXI work");
   $display("PASS idle complete metadata flushed without publication or AXI work");
   send_frame('h3800,PIXELS);check_frame('h3800,BANK0,11);
   idle();@(negedge clk);
   camera.capture_open = 1;
   camera.capture_bad = 1;
   camera.pixel_count = 13;
   camera.pixel_limit = PIXELS;
   repeat(24) @(negedge clk);
   if(camera.capture_stop || abort_req || camera.capture_open)
     $fatal(1,"idle bad capture remains permanently closed");
   if(last_cnt!=11 || state!=1 || cv || av || bus_active)
     $fatal(1,"bad orphan recovery fabricated completion or AXI work");
   $display("PASS idle bad metadata flushed without publication or AXI work");
   send_frame('h4800,PIXELS);check_frame('h4800,BANK1,12);
if(aw_count!=b_count||bus_active||left!=0||zero_strobes==0)$fatal(1,"final AXI ledger mismatch");
  $display("PASS CAM5 IDLE RECOVERY success=%0d abort=%0d AW=%0d B=%0d zero-strobe filler=%0d",success_count,abort_count,aw_count,b_count,zero_strobes);
  $finish;
 end
 initial begin #3000000;$fatal(1,"frame recovery timeout state=%0d abort=%0d last=%0d",state,abort_count,last_cnt);end
endmodule
