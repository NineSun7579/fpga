`timescale 1ns/1fs
module tb_throughput;
GTP_GRS GRS_INST(.GRS_N(1'b1));
parameter GATED=0;
parameter AXI_RATE4=400; // 400=100MHz stress; actual DDR PLL is 525=131.25MHz
reg clk=0; always #(2000.0/AXI_RATE4) clk=~clk;
reg rst=1;
wire [2:0] cr,dr,done,av,ar,wv,wr,wl,bv,br,aborted,abort_req,cv,dv;
wire [7:0] al[0:2];
wire [31:0] aa[0:2],ca[0:2],clen[0:2];
wire [127:0] wd[0:2],din[0:2];
wire [15:0] ws[0:2],credits[0:2];
wire [31:0] faults[0:2],rejects[0:2];
reg [15:0] pix[0:2];
reg [2:0] pv=0,vs=0;
integer successes[0:2],aborts[0:2],offered[0:2],received[0:2],aws[0:2],bs[0:2],starve[0:2];
integer maxcredits[0:2],runread[0:2],maxread[0:2],awtime[0:2],maxtenure[0:2];
realtime firstdone[0:2],lastdone[0:2];
integer frames=1, phase=0, latency=8, gap=1;
integer tick=0;
wire pop;
function [15:0] pattern(input integer c,input integer n);
pattern=(n ^ (n>>16) ^ (c*16'h3141));
endfunction
genvar g;
generate for(g=0;g<3;g=g+1) begin:D
ov5640_ddr #(.DATA_WIDTH(16),.CAM_DATA_LEN(38400)) cap(
 .axi_clk(clk),.axi_rst(rst),.dma_abort(aborted[g]),.dma_abort_req(abort_req[g]),.dma_done(done[g]),.axi_cam_en(1'b1),
 .cam_data_addr_1(32'h100000+g*32'h200000),.cam_data_addr_2(32'h200000+g*32'h200000),.cam_data_len(17'd38400),
 .s_data(pix[g]),.s_data_valid(pv[g]),.s_vsync(vs[g]),.s_hsync(1'b0),
 .axi_data(din[g]),.axi_data_valid(dv[g]),.axi_data_ready(dr[g]),
 .axi_cmd_addr(ca[g]),.axi_cmd_len(clen[g]),.axi_cmd_valid(cv[g]),.axi_cmd_ready(cr[g]),
 .xdma_ack(2'b00),.dbg_fault_snapshot(faults[g]),.dbg_reject_counts(rejects[g])
 `ifdef CREDIT_PORTS
 ,.axi_data_available(credits[g])
 `endif
);
axi_dma_write #(.BURST_LEN(16)
 `ifdef CREDIT_PORTS
 ,.WAIT_FOR_DATA(GATED)
 `endif
) dut(
 .clk(clk),.rst(rst),.abort_req(abort_req[g]),.data_in_abort(aborted[g]),
 .cmd_valid(cv[g]),.cmd_ready(cr[g]),.cmd_addr(ca[g]),.cmd_len(clen[g]),.cmd_id(g),
 .data_in(din[g]),.data_in_keep(16'hffff),.data_in_valid(dv[g]),.data_in_ready(dr[g]),.data_in_last(done[g]),
 `ifdef CREDIT_PORTS
 .data_in_available(credits[g]),
 `endif
 .m_axi_awaddr(aa[g]),.m_axi_awlen(al[g]),.m_axi_awvalid(av[g]),.m_axi_awready(ar[g]),
 .m_axi_wdata(wd[g]),.m_axi_wstrb(ws[g]),.m_axi_wlast(wl[g]),.m_axi_wvalid(wv[g]),.m_axi_wready(wr[g]),
 .m_axi_bid(4'd0),.m_axi_bresp(2'd0),.m_axi_bvalid(bv[g]),.m_axi_bready(br[g]));
integer row,col,f,n,acc,cyc,idx,j,leftw;
reg payload;
reg awheld=0,wheld=0;
reg [39:0] awsave;
reg [144:0] wsave;
initial begin
 successes[g]=0;aborts[g]=0;offered[g]=0;received[g]=0;aws[g]=0;bs[g]=0;starve[g]=0;pix[g]=0;
 maxcredits[g]=0;runread[g]=0;maxread[g]=0;maxtenure[g]=0;firstdone[g]=0;lastdone[g]=0;
 wait(!rst);repeat(20+(g==2?phase:0)) @(negedge clk);
 for(f=0;f<frames;f=f+1) begin
  vs[g]=1;repeat(16)@(negedge clk);vs[g]=0;
  repeat(100)@(negedge clk);n=0;acc=0;
  // 84/48 MHz byte clocks, RGB565 two bytes/pixel. HTS=1896 VTS=984.
  // NCO maps asynchronous source rate to AXI clock without rounding drift.
  for(row=0;row<984;row=row+1) begin
   col=0;
   while(col<1896) begin
    @(negedge clk);pv[g]=0;acc=acc+(g==2?192:336);
    if(acc>=AXI_RATE4) begin
     acc=acc-AXI_RATE4;
     if(row<480 && col<1280 && (col%2)==1) begin
      pix[g]=pattern(g,n);pv[g]=1;n=n+1;offered[g]=offered[g]+1;
     end
     col=col+1;
    end
   end
  end
  @(negedge clk);pv[g]=0;
 end
end
always @(posedge clk) if(!rst) begin
 if(awheld && (!av[g] || {aa[g],al[g]}!==awsave))$fatal(1,"AW unstable");
 if(wheld && (!wv[g] || {wd[g],ws[g],wl[g]}!==wsave))$fatal(1,"W unstable");
 awheld<=av[g]&&!ar[g];awsave<={aa[g],al[g]};
 wheld<=wv[g]&&!wr[g];wsave<={wd[g],ws[g],wl[g]};
 if(done[g]&&aborted[g])$fatal(1,"success/abort overlap");
 if(cap.capture_flush&&(dut.trans||av[g]||wv[g]))$fatal(1,"flush before retirement");
 if(av[g]&&ar[g])begin aws[g]=aws[g]+1;leftw=al[g]+1;payload=al[g]!=0;awtime[g]=tick;end
 if(credits[g]>maxcredits[g])maxcredits[g]=credits[g];
 if(cap.ov5640_ddr_w.rd_en_drm)runread[g]=runread[g]+1;else runread[g]=0;
 if(runread[g]>maxread[g])maxread[g]=runread[g];
 if(arb.busy && arb.owner==g && !wv[g] && !dut.w_done)starve[g]=starve[g]+1;
 if(wv[g]&&wr[g])begin
  if(leftw==0)$fatal(1,"W without obligation");
  if(wl[g] !== (leftw==1))$fatal(1,"WLAST ledger");leftw=leftw-1;
  if(payload && ws[g]==16'hffff)begin
   if(GATED)for(j=0;j<8;j=j+1)if(wd[g][j*16+:16]!==pattern(g,received[g]%307200+j))$fatal(1,"pixel mismatch cam=%0d n=%0d got=%h",g,received[g]+j,wd[g]);
   received[g]=received[g]+8;
  end
  if(GATED && !payload && wd[g][31:0]!==successes[g]+1)$fatal(1,"wrong tag sequence");
 end
 if(bv[g]&&br[g])begin if(leftw!=0)$fatal(1,"early B");bs[g]=bs[g]+1;if(tick-awtime[g]>maxtenure[g])maxtenure[g]=tick-awtime[g];end
 if(done[g] && !payload)begin
  successes[g]=successes[g]+1;if(successes[g]==1)firstdone[g]=$realtime;lastdone[g]=$realtime;
 end
 if(aborted[g])begin aborts[g]=aborts[g]+1;$display("REJECT cam=%0d fault=%h at=%0t",g+1,faults[g],$time);end
end
end endgenerate
wire [7:0] sal;
wire [127:0] swd;
wire [15:0] sws;
wire sav,sar,swv,swr,swl,sbv,sbr;
ddr_w_arb arb(.clk(clk),.rst(rst),
 .m0_awid(4'd1),.m0_awaddr(aa[0]),.m0_awlen(al[0]),.m0_awsize(3'd4),.m0_awburst(2'd1),.m0_awlock(1'b0),.m0_awcache(4'd3),.m0_awprot(3'd0),.m0_awvalid(av[0]),.m0_awready(ar[0]),.m0_wdata(wd[0]),.m0_wstrb(ws[0]),.m0_wlast(wl[0]),.m0_wvalid(wv[0]),.m0_wready(wr[0]),.m0_bvalid(bv[0]),.m0_bready(br[0]),
 .m1_awid(4'd4),.m1_awaddr(aa[1]),.m1_awlen(al[1]),.m1_awsize(3'd4),.m1_awburst(2'd1),.m1_awlock(1'b0),.m1_awcache(4'd3),.m1_awprot(3'd0),.m1_awvalid(av[1]),.m1_awready(ar[1]),.m1_wdata(wd[1]),.m1_wstrb(ws[1]),.m1_wlast(wl[1]),.m1_wvalid(wv[1]),.m1_wready(wr[1]),.m1_bvalid(bv[1]),.m1_bready(br[1]),
 .m2_awid(4'd2),.m2_awaddr(aa[2]),.m2_awlen(al[2]),.m2_awsize(3'd4),.m2_awburst(2'd1),.m2_awlock(1'b0),.m2_awcache(4'd3),.m2_awprot(3'd0),.m2_awvalid(av[2]),.m2_awready(ar[2]),.m2_wdata(wd[2]),.m2_wstrb(ws[2]),.m2_wlast(wl[2]),.m2_wvalid(wv[2]),.m2_wready(wr[2]),.m2_bvalid(bv[2]),.m2_bready(br[2]),
 .s_wdata(swd),.s_wstrb(sws),.s_awlen(sal),.s_awvalid(sav),.s_awready(sar),.s_wvalid(swv),.s_wready(swr),.s_wlast(swl),.s_bvalid(sbv),.s_bready(sbr),.s_bid(4'd0),.s_bresp(2'd0));

// Cycle-accurate top.v hold/stage/AW/B contract, programmable DDR IP service.
wire [3:0] dal=sal;
reg holdv=0,ipv=0,bvalid=0;
reg [3:0] heldlen;
integer level=0,left=0,delayleft=0;
wire [4:0] stage_level;
wire stage_full,stage_empty;
wire [143:0] stage_data;
reg [143:0] stage_expected[0:15];
integer wp=0,rp=0;
ddr_fifo16_w stage(.clk(clk),.rst(rst),.wr_data({sws,swd}),.wr_en(swv),
 .wr_water_level(stage_level),.full(stage_full),.almost_full(),.rd_data(stage_data),
 .rd_en(pop),.empty(stage_empty),.almost_empty());
assign sar=sav&&!ipv&&!holdv&&stage_empty&&(dal<(16-stage_level))&&!bvalid;
assign swr=!stage_full;
assign sbv=bvalid;
assign pop=(left>0)&&(delayleft==0)&&(tick%gap==0);
always @(posedge clk) begin
 if(rst)begin holdv<=0;ipv<=0;bvalid<=0;level<=0;left<=0;tick<=0;end
 else begin
  tick<=tick+1;
  if(delayleft>0)delayleft<=delayleft-1;
  case({swv&&swr,pop})2'b10:level<=level+1;2'b01:level<=level-1;endcase
  if(sar)begin holdv<=1;heldlen<=dal;end
  if(holdv&&!ipv&&(stage_level>=heldlen+1)&&!stage_empty)begin holdv<=0;ipv<=1;end
  else if(ipv)begin ipv<=0;left<=heldlen+1;delayleft<=latency;end
  if(swv&&swr)begin stage_expected[wp]= {sws,swd};wp=(wp+1)%16;end
  if(pop)begin
   if(stage_empty)$fatal(1,"DDR ghost read");
   if(stage_data!==stage_expected[rp])$fatal(1,"DDR staging data mismatch");rp=(rp+1)%16;
   left<=left-1;if(left==1)bvalid<=1;
  end
  if(sbv&&sbr)bvalid<=0;
 end
end
integer i;
initial begin
 if($value$plusargs("FRAMES=%d",frames))begin end
 if($value$plusargs("PHASE=%d",phase))begin end
 if($value$plusargs("LATENCY=%d",latency))begin end
 if($value$plusargs("GAP=%d",gap))begin end
 repeat(20)@(negedge clk);rst=0;
 repeat(frames*9717*AXI_RATE4+phase+10000)@(negedge clk);
 for(i=0;i<3;i=i+1)begin
  $display("RESULT gated=%0d cam=%0d offered=%0d received=%0d success=%0d abort=%0d reject=%h AW=%0d B=%0d owner_starve=%0d",GATED,i+1,offered[i],received[i],successes[i],aborts[i],rejects[i],aws[i],bs[i],starve[i]);
  $display("PERF cam=%0d max_stored_beats=%0d max_consecutive_DRM_reads=%0d max_AW_to_B_cycles=%0d completion_fps=%f",i+1,maxcredits[i],maxread[i],maxtenure[i],successes[i]>1 ? (successes[i]-1)*1.0e9/(lastdone[i]-firstdone[i]) : 0.0);
  if(aws[i]!=bs[i])$fatal(1,"unbalanced AW B");
  if(GATED && (successes[i]!=frames||aborts[i]!=0||received[i]!=frames*307200))$fatal(1,"gated throughput failure");
 end
 if(!GATED && (aborts[0]==0||aborts[1]==0||successes[2]!=frames))$fatal(1,"baseline not reproduced");
 $display("PASS throughput");$finish;
end
endmodule
