`timescale 1ns/1ps
module tb_frame_boundary_dummy;
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
 integer case_id=0, failures=0, published=0, dropped=0;
 integer kind,phase,gap,extra, seed_new, old_last=0;
 integer accept_n=0, first_pixel=-1, sof_cycle=-1, admit_cycle=-1;
 reg trace_on=0;
 always @(posedge clk) if(!rst && trace_on) begin
   if(camera.raw_sof) begin
     sof_cycle=cycle;
     $display("TRACE case=%0d SOF cycle=%0d flush=%0d count=%0d complete=%b busy=%b",case_id,cycle,camera.flush_count,camera.pixel_count,camera.capture_complete,camera.engine_busy);
   end
   if(camera.m_vsync) begin
     admit_cycle=cycle;accept_n=0;first_pixel=-1;
     $display("TRACE case=%0d ADMIT cycle=%0d flush=%0d",case_id,cycle,camera.flush_count);
   end
   if(camera.m_data_valid) begin
     if(accept_n==0)begin first_pixel=pixel;$display("TRACE case=%0d FIRST cycle=%0d pixel=%h",case_id,cycle,pixel);end
     accept_n=accept_n+1;
   end
   if(done) $display("TRACE case=%0d DONE cycle=%0d tag=%b count=%0d good=%b",case_id,cycle,cur_tag,camera.pixel_count,camera.frame_good);
 end
 task automatic fresh;
 begin
   trace_on=0;sv=0;pv=0;ack=0;
   idle();rst=1;repeat(6)@(negedge clk);rst=0;idle();
   case_id=case_id+1;accept_n=0;first_pixel=-1;sof_cycle=-1;admit_cycle=-1;
   for(integer z=0;z<196608;z=z+1)mem[z]=8'hcc;
   trace_on=1;
 end endtask
 task automatic pulse_and_pixels(input integer blank,input integer count);
 begin
   sv=1;
   if(blank==0) begin
     pixel=seed_new;pv=1;@(negedge clk);sv=0;
     for(integer z=1;z<count;z=z+1)begin pixel=seed_new+z;@(negedge clk);end
     pv=0;
   end else begin
     @(negedge clk);sv=0;
     repeat(blank-1)@(negedge clk);
     pixels(seed_new,count);
   end
 end endtask
 task automatic verify_bank(input integer bank,input integer seed,input integer seq);
 integer mismatches;reg [15:0] actual;
 begin
   mismatches=0;
   for(integer z=0;z<PIXELS;z=z+1)begin
     actual={mem[bank+z*2+1],mem[bank+z*2]};
     if(actual!==16'(seed+z))begin
       if(mismatches==0)$display("BAD_PUBLISHED case=%0d kind=%0d phase=%0d gap=%0d extra=%0d seq=%0d index=%0d actual=%h expected=%h sof=%0d admit=%0d first=%h",case_id,kind,phase,gap,extra,seq,z,actual,16'(seed+z),sof_cycle,admit_cycle,16'(first_pixel));
       mismatches=mismatches+1;
     end
   end
   if(mismatches!=0)failures=failures+1;
   if({mem[bank+WORDS*16+3],mem[bank+WORDS*16+2],mem[bank+WORDS*16+1],mem[bank+WORDS*16]}!==seq)$fatal(1,"tag mismatch");
   $display("VERIFY case=%0d seq=%0d mismatch=%0d pixels=%0d",case_id,seq,mismatches,PIXELS);
 end endtask
 task automatic settle;
 begin
   repeat(1200)@(negedge clk);idle();
   if(kind==0)begin
     if(last_cnt==1)begin verify_bank(BANK0,seed_new,1);published=published+1;end
     else if(last_cnt==0)dropped=dropped+1;
     else $fatal(1,"unexpected flush publication count");
   end else begin
     if(last_cnt>=1)verify_bank(BANK0,'h1000,1);
     if(last_cnt==2)begin verify_bank(BANK1,seed_new,2);published=published+1;end
     else dropped=dropped+1;
     if(last_cnt>2)$fatal(1,"unexpected boundary publication count");
   end
   $display("RESULT case=%0d kind=%0d phase=%0d gap=%0d extra=%0d last=%0d accepted=%0d first=%h",case_id,kind,phase,gap,extra,last_cnt,accept_n,16'(first_pixel));
   if(aw_count!=b_count||bus_active||left!=0)$fatal(1,"boundary AXI ledger mismatch");
 end endtask
 initial begin
   for(j=0;j<196608;j=j+1)mem[j]=8'hcc;
   repeat(6)@(negedge clk);rst=0;idle();
   kind=0;
   for(extra=1;extra<=1;extra=extra+1)
   for(phase=0;phase<=6;phase=phase+1)
   for(gap=0;gap<=8;gap=gap+1)begin
     fresh();seed_new='h4000;
     send_frame('h2000,13);
     wait(camera.flush_count==4);@(negedge clk);
     repeat(phase)@(negedge clk);
     $display("CASE %0d FLUSH phase=%0d gap=%0d extra=%0d",case_id,phase,gap,extra);
     pulse_and_pixels(gap,PIXELS+extra);settle();
   end
   extra=0;gap=8;
   for(kind=1;kind<=0;kind=kind+1)
   for(phase=0;phase<=8;phase=phase+1)begin
     fresh();seed_new='h6000;
     $display("CASE %0d BOUNDARY kind=%0d phase=%0d gap=%0d",case_id,kind,phase,gap);
     if(kind==1)begin
       sof();
       fork
         pixels('h1000,PIXELS);
         begin repeat(PIXELS-4+phase)@(negedge clk);pulse_and_pixels(gap,PIXELS);end
       join
     end else begin
       send_frame('h1000,PIXELS);
       if(kind==2)wait(wv&&wr&&wl&&!cur_tag&&(offset==BANK0+WORDS*16-16));
       else wait(wv&&wr&&wl&&cur_tag);
       @(negedge clk);repeat(phase)@(negedge clk);
       pulse_and_pixels(gap,PIXELS);
     end
     settle();
   end
   $display("BOUNDARY SUMMARY cases=%0d published_new=%0d dropped_new=%0d bad_published=%0d FIFO_WORDS=%0d",case_id,published,dropped,failures,WORDS);
   $finish;
 end
 initial begin #100000000;$fatal(1,"boundary timeout case=%0d kind=%0d phase=%0d gap=%0d state=%0d",case_id,kind,phase,gap,state);end
endmodule
