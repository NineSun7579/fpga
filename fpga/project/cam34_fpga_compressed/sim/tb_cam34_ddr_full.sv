`timescale 1ns/1ps
module tb_cam34_ddr_full;
`ifdef VENDOR_FIFO
 localparam WORDS=2048;
 GTP_GRS GRS_INST(.GRS_N(1'b1));
`else
 localparam WORDS=9600;
`endif
 localparam W=640,H=480,SOURCE_PIXELS=W*H,PIXELS=WORDS*8, BANK0=32'h10000, BANK1=32'h40000;
 localparam LEN_WIDTH=$clog2(WORDS)+1;
 reg clk=0;always #5 clk=~clk;
 reg auto_ack=1;
 reg rst=1,sv=0,pv=0;reg [15:0] pixel=0;
 wire [31:0] ca,cl,awaddr,last_cnt,state,prev_base;
 wire cv,cr,dv,dr,done,aborted,abort_req,av,ar,wv,wr,wl,br;
 wire [127:0] data,wd;wire [15:0] ws;wire [7:0] al;
 wire [1:0] req;reg [1:0] ack=0;
 wire[15:0]compact_pixel,available;wire compact_valid,compact_vsync,compact_hsync;
 ov5640_ddr #(.DATA_WIDTH(16),.CAM_DATA_LEN(WORDS)) camera(
  .axi_data_available(available),.lease_prev_base(),.lease_bank0(),.lease_bank1(),.lease_sequence(),.lease_published(),.lease_writer_idle(),.lease_pending(),.lease_flush(),
  .dbg_fault_snapshot(),.dbg_reject_counts(),.dbg_input_pixels(),.axi_clk(clk),.axi_rst(rst),.dma_done(done),.dma_abort(aborted),.dma_abort_req(abort_req),
  .axi_cam_en(1'b1),.cam_data_addr_1(BANK0),.cam_data_addr_2(BANK1),.cam_data_len(LEN_WIDTH'(WORDS)),
  .s_data(compact_pixel),.s_data_valid(compact_valid),.s_hsync(1'b1),.s_vsync(compact_vsync),
  .axi_data(data),.axi_data_valid(dv),.axi_data_ready(dr),.axi_data_last(),
  .axi_cmd_addr(ca),.axi_cmd_len(cl),.axi_cmd_valid(cv),.axi_cmd_ready(cr),
  .xdma_req(req),.xdma_ack(ack),.dbg_last_cnt(last_cnt),.dbg_state(state),.prev_frame_base(prev_base),
  .dbg_axi_cnt(),.dbg_axi_num(),.dbg_zdin(),.dbg_zout(),.dbg_wd_cnt());
 
 cam34_downsample_2x2 #(.IN_W(W),.IN_H(H)) down(.clk(clk),.rst(rst),.in_valid(pv),.in_pixel(pixel),.in_hsync(1'b1),.in_vsync(sv),.out_valid(compact_valid),.out_pixel(compact_pixel),.out_hsync(compact_hsync),.out_vsync(compact_vsync));
 function[15:0]mean_pixel(input integer idx,input integer seed);
 integer x,y,n,v,r,g,b,a,c,d;begin x=(idx%(W/2))*2;y=(idx/(W/2))*2;r=0;g=0;b=0;
 for(n=0;n<4;n=n+1)begin v=16'(seed+(y+n/2)*W+x+n%2);a=(v>>11)&31;c=(v>>5)&63;d=v&31;r+=((a<<3)|(a>>2));g+=((c<<2)|(c>>4));b+=((d<<3)|(d>>2));end
 mean_pixel=((((r+2)/4)>>3)<<11)|((((g+2)/4)>>2)<<5)|(((b+2)/4)>>3);
 end endfunction
 reg stall_aw=0,stall_w=0,stall_b=0,tag_error=0,data_error=0;
 reg bv=0;reg [1:0] resp=0;
 axi_dma_write #(.WAIT_FOR_DATA(1),.BURST_LEN(16),.WD_LIMIT(4096)) dma(
  .data_in_available(available),.lease_idle(),.clk(clk),.rst(rst),.abort_req(abort_req),.data_in_abort(aborted),
  .cmd_addr(ca),.cmd_len(cl),.cmd_valid(cv),.cmd_ready(cr),.cmd_id(4'd1),
  .data_in(data),.data_in_keep(16'hffff),.data_in_valid(dv),.data_in_ready(dr),.data_in_last(done),
  .m_axi_awaddr(awaddr),.m_axi_awlen(al),.m_axi_awvalid(av),.m_axi_awready(ar),
  .m_axi_awid(),.m_axi_awsize(),.m_axi_awburst(),.m_axi_awlock(),.m_axi_awcache(),.m_axi_awprot(),
  .m_axi_wdata(wd),.m_axi_wstrb(ws),.m_axi_wlast(wl),.m_axi_wvalid(wv),.m_axi_wready(wr),
  .m_axi_bvalid(bv&&!stall_b),.m_axi_bready(br),.m_axi_bresp(resp),.m_axi_bid(4'd1));
 integer cycle=0,left=0,bdelay=0,offset=0,aw_count=0,b_count=0,abort_count=0,tag_count=0;
 integer success_count=0,zero_strobes=0;
 reg bus_active=0,cur_tag=0;
 reg [7:0] mem[0:524287];
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
   if(actual!==mean_pixel(i,seed))$fatal(1,"pixel alignment bank=%h index=%0d got=%h expected=%h",bank,i,actual,mean_pixel(i,seed));
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

 integer before_count,before_tags;
 initial begin
  for(j=0;j<524288;j=j+1)mem[j]=8'hcc;
  repeat(6)@(negedge clk);rst=0;idle();
  send_frame('h1000,SOURCE_PIXELS);check_frame('h1000,BANK0,1);
  $display("[PASS] actual packer+DMA writes compressed raster and tag at +153600 only after B");
  send_frame('h3000,SOURCE_PIXELS+8);check_frame('h3000,BANK1,2);
  $display("[PASS] tail dummy never enters the compressed DDR payload");
  before_count=abort_count;before_tags=tag_count;
  send_frame('h5000,143);sof();wait(abort_count>before_count);idle();
  if(last_cnt!=2||tag_count!=before_tags)$fatal(1,"short compressed raster published a tag");
  send_frame('h7000,SOURCE_PIXELS);check_frame('h7000,BANK0,3);
  $display("[PASS] incomplete source never publishes commit, subsequent complete frame recovers");
  send_frame('h9000,SOURCE_PIXELS);wait(cur_tag);@(negedge clk);stall_b=1;
  wait(bv);repeat(100)@(negedge clk);
  if(last_cnt!=3||prev_base!=BANK0)$fatal(1,"compressed tag published before real B response");
  stall_b=0;check_frame('h9000,BANK1,4);
  if(aw_count!=b_count||bus_active||left!=0)$fatal(1,"DMA ledger mismatch");
  $display("CAM34_DDR_FULL_PASS frames=%0d bytes=%0d AW=%0d B=%0d",success_count,WORDS*16,aw_count,b_count);$finish;
 end
 initial begin #25000000;$fatal(1,"compressed DDR test timeout state=%0d abort=%0d last=%0d",state,abort_count,last_cnt);end
endmodule
