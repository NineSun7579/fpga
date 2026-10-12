`timescale 1ns/1ps
module tb_frame_recovery;
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
 wire ts,tv,tbad,tp; wire [15:0] tpx;
 wire quiet,q; wire [3071:0] rec;
 wire [31:0] ba; wire [7:0] bl; wire bav,bwv,bwl,bbr;
 wire [127:0] bwd; wire [15:0] bws;
 reg bbv=0; integer bleft=0,boff=0,bbeat=0,baw=0,bb=0,btag=0;
 integer seed_seen=0,first_pixel=1,bcam_bank=0,bi,bindex,bexpect,success_bg=0,raw_flush_pulses=0;
 reg [15:0] bm[0:524287]; reg [1:0] old0=0,old1=0;
 background_six #(.WIDTH(32),.HEIGHT(16),.DEADLINE(1048576)) branch(
 .clk(clk),.rst(rst),.enable(1'b1),.invalidate(12'd0),
 .sof({5'd0,ts}),.pixel_valid({5'd0,tv}),.source_bad({5'd0,tbad}),
 .raw_publish({5'd0,tp}),.pixels({80'd0,tpx}),.source_sequence({160'd0,last_cnt}),
 .quiescent(quiet),.quarantine(q),.records(rec),.awaddr(ba),.awlen(bl),
 .awvalid(bav),.awready(!bbv && bleft==0),.wdata(bwd),.wstrb(bws),
  .wvalid(bwv),.wlast(bwl),.wready(1'b1),.bresp(2'd0),.bvalid(bbv),.bready(bbr));
  reg [51:0] previous_tap=0;
  integer tap_edges=0,aligned_sofs=0,aligned_publications=0,aligned_faults=0;
  always @(posedge clk) begin
   if(rst) previous_tap=0;
   else begin
    if({branch.cameras[0].producer.sof,branch.cameras[0].producer.pixel_valid,
        branch.cameras[0].producer.source_bad,branch.cameras[0].producer.raw_publish,
        branch.cameras[0].producer.pixel,branch.cameras[0].producer.source_sequence}!==previous_tap)
     $fatal(1,"real RAW chain tap tuple phase mismatch");
    tap_edges=tap_edges+1;
    if(previous_tap[51])aligned_sofs=aligned_sofs+1;
    if(previous_tap[48])aligned_publications=aligned_publications+1;
    if(previous_tap[49])aligned_faults=aligned_faults+1;
    previous_tap={ts,tv,tbad,tp,tpx,last_cnt};
   end
  end
 always @(posedge clk) if(!rst) begin
  if(tp)begin
   if(tbad || !camera.capture_flush)$fatal(1,"RAW counter pulse must export during nonfault local flush");
   raw_flush_pulses=raw_flush_pulses+1;
  end
  if(ts)first_pixel=1;
  if(tv && first_pixel)begin seed_seen=tpx;first_pixel=0;end
  if(bav && !bbv && bleft==0)begin
   baw=baw+1;bleft=bl+1;boff=ba-32'h0a280000;bbeat=0;
   bcam_bank=boff/32'h40000;
   if(rec[bcam_bank*256+:2]!=1)$fatal(1,"RAW chain guard before AW");
  end
  if(bwv && bleft>0)begin
   if(bwl!=(bleft==1))$fatal(1,"chain WLAST");
   for(bi=0;bi<8;bi=bi+1)if(bws[bi*2+:2]==3)bm[boff+bbeat*8+bi]=bwd[bi*16+:16];
   if(boff%32'h40000==256)btag=btag+1;
   bbeat=bbeat+1;bleft=bleft-1;if(bleft==0)bbv<=1;
  end
  if(bbv && bbr)begin bbv<=0;bb=bb+1;end
  if(rec[1:0]==2 && old0!=2)verify_bg(0);
  if(rec[257:256]==2 && old1!=2)verify_bg(1);
  old0<=rec[1:0];old1<=rec[257:256];
 end
 task verify_bg(input integer bank);
 integer i,expected;
 begin
  if(rec[bank*256+128+:32]!==last_cnt)$fatal(1,"chain sequence not hardware RAW counter");
  if({bm[bank*262144+257],bm[bank*262144+256]}!==last_cnt)$fatal(1,"chain memory tag");
  for(i=0;i<128;i=i+1)begin
   expected=(seed_seen+(i/16)*64+(i%16)*2)%65536;
   if(bm[bank*262144+i]!==16'(expected))$fatal(1,"chain CPU even-coordinate pixel %0d",i);
  end
  success_bg=success_bg+1;
  $display("EXTRA_RAW_PUBLICATION bank=%0d hardware_counter=%h pixels=128",bank,last_cnt);
 end endtask
 ov5640_ddr #(.DATA_WIDTH(16),.CAM_DATA_LEN(WORDS)) camera(
 .bg_sof(ts),.bg_valid(tv),.bg_bad(tbad),.bg_raw_publish(tp),.bg_pixel(tpx),
  .axi_clk(clk),.axi_rst(rst),.dma_done(done),.dma_abort(aborted),.dma_abort_req(abort_req),
  .axi_cam_en(1'b1),.cam_data_addr_1(BANK0),.cam_data_addr_2(BANK1),.cam_data_len(LEN_WIDTH'(WORDS)),
  .s_data(pixel),.s_data_valid(pv),.s_hsync(1'b1),.s_vsync(sv),
  .axi_data(data),.axi_data_valid(dv),.axi_data_ready(dr),.axi_data_last(),
  .axi_cmd_addr(ca),.axi_cmd_len(cl),.axi_cmd_valid(cv),.axi_cmd_ready(cr),
  .xdma_req(req),.xdma_ack(ack),.dbg_last_cnt(last_cnt),.dbg_state(state),.prev_frame_base(prev_base),
  .dbg_axi_cnt(),.dbg_axi_num(),.dbg_zdin(),.dbg_zout(),.dbg_wd_cnt());
 reg stall_aw=0,stall_w=0,stall_b=0,tag_error=0,data_error=0;
 reg bv=0;reg [1:0] resp=0;
 axi_dma_write #(.BURST_LEN(16),.WD_LIMIT(64)) dma(
  .clk(clk),.rst(rst),.abort_req(abort_req),.data_in_abort(aborted),
  .cmd_addr(ca),.cmd_len(cl),.cmd_valid(cv),.cmd_ready(cr),.cmd_id(4'd1),
  .data_in(data),.data_in_keep(16'hffff),.data_in_valid(dv),.data_in_ready(dr),.data_in_last(done),
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
  send_frame('h4000,11);failed_frame(a,t,s);
  $display("PASS missing data watchdog abort without another SOF");
  send_frame('h5000,PIXELS);check_frame('h5000,BANK0,3);
  // AW offered then source abort: AW must survive until actually accepted.
  a=abort_count;t=tag_count;s=last_cnt;stall_aw=1;
  send_frame('h6000,13);sof();repeat(30)@(negedge clk);
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
  wait(quiet); if(success_bg!=6 || rec[257:256]!=0)$fatal(1,"failed RAW tag B published thumbnail");
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
  if(success_bg!=9 || rec[1:0]!=1)$fatal(1,"thumbnail published before delayed RAW tag B");
  stall_b=0;check_frame('h2800,BANK1,10);
  $display("PASS tag B backpressure longer than WD_LIMIT never publishes early");
  if(aw_count!=b_count||bus_active||left!=0||zero_strobes==0)$fatal(1,"final AXI ledger mismatch");
  $display("PASS FRAME RECOVERY success=%0d abort=%0d AW=%0d B=%0d zero-strobe filler=%0d",success_count,abort_count,aw_count,b_count,zero_strobes);
   wait(quiet); repeat(8)@(negedge clk);
   if(success_bg!=10)$fatal(1,"missing real RAW/background successes %0d",success_bg);
   // Deposit only initial counter state to reach wrap without 2^32 frames.
   camera.ov5640_ddr_w_ctrl.last_cnt=32'hffffffff;
   camera.ov5640_ddr_w_ctrl.frame_cnt=32'hffffffff;
   camera.bg_sequence_q=32'hffffffff;
   send_frame('h3800,PIXELS);check_frame('h3800,BANK0,0);
   repeat(8)@(negedge clk);
   if(success_bg!=11 || raw_flush_pulses!=11 || baw!=bb || !quiet || q)$fatal(1,"chain final ledger");
    $display("EXTRA_RAW_CHAIN_PASS successes=%0d background_AW=%0d B=%0d tags=%0d RAW_AW=%0d RAW_B=%0d wrap_counter=%h successful_flush_exports=%0d",success_bg,baw,bb,btag,aw_count,b_count,last_cnt,raw_flush_pulses);
    if(aligned_publications!=11 || aligned_sofs<11 || aligned_faults==0)$fatal(1,"missing actual-chain tap events");
    $display("EXTRA_TAP_PHASE_PASS edges=%0d sofs=%0d publications=%0d fault_cycles=%0d latency=1",tap_edges,aligned_sofs,aligned_publications,aligned_faults);
   $finish;
 end
 initial begin #3000000;$fatal(1,"frame recovery timeout state=%0d abort=%0d last=%0d",state,abort_count,last_cnt);end
endmodule
