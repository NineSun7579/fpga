`timescale 1ns/1ps
module tb_timeout_recovery;
reg clk=0; always #5 clk=~clk;
reg rst=1;
reg [2:0] cv=0, dv=0;
reg [31:0] clen[0:2];
wire [2:0] aborted;
wire [2:0] cr,dr,done,av,ar,wv,wr,wl,bv,br;
wire [7:0] al[0:2];
wire [31:0] aa[0:2];
wire [127:0] wd[0:2];
wire [15:0] ws[0:2];
integer aborts[0:2];
integer ac[0:2],bc[0:2],wc[0:2],dc[0:2];
genvar g;
generate for(g=0;g<3;g=g+1) begin:D
 reg pending_aw=0;
 reg [39:0] saved_aw;
 axi_dma_write #(.BURST_LEN(16)) dut(
 .abort_req(1'b0),.data_in_abort(aborted[g]),
 .clk(clk),.rst(rst),.cmd_valid(cv[g]),.cmd_ready(cr[g]),.cmd_addr(32'h1000+g*32'h10000),.cmd_len(clen[g]),.cmd_id(g),
 .data_in(128'h12345678),.data_in_keep(16'hffff),.data_in_valid(dv[g]),.data_in_ready(dr[g]),.data_in_last(done[g]),
 .m_axi_awaddr(aa[g]),.m_axi_awlen(al[g]),.m_axi_awvalid(av[g]),.m_axi_awready(ar[g]),
 .m_axi_wdata(wd[g]),.m_axi_wstrb(ws[g]),.m_axi_wlast(wl[g]),.m_axi_wvalid(wv[g]),.m_axi_wready(wr[g]),
 .m_axi_bid(4'd0),.m_axi_bresp(2'd0),.m_axi_bvalid(bv[g]),.m_axi_bready(br[g]));
 always @(posedge clk) if(!rst) begin
  if(pending_aw && (!av[g] || {aa[g],al[g]}!==saved_aw))$fatal(1,"AW changed under backpressure cam=%0d",g+1);
  pending_aw<=av[g]&&!ar[g];saved_aw<={aa[g],al[g]};
  if(av[g]&&ar[g]) begin ac[g]=ac[g]+1; $display("AW t=%0t cam=%0d len=%0d",$time,g+1,al[g]); end
  if(wv[g]&&wr[g]) wc[g]=wc[g]+1;
  if(g==2&&wv[g]&&wr[g]&&(wd[g]!==128'd0||ws[g]!==16'h0000))$fatal(1,"timeout fill is not zero/zero strobe");
  if(bv[g]&&br[g]) bc[g]=bc[g]+1;
  if(done[g]&&aborted[g])$fatal(1,"done and abort overlap");
  if(aborted[g])aborts[g]=aborts[g]+1;
  if(g==2&&done[g])$fatal(1,"abort incorrectly reported success");
  if(done[g]||aborted[g]) begin dc[g]=dc[g]+1; $display("DONE t=%0t cam=%0d aw=%0d b=%0d w=%0d",$time,g+1,ac[g],bc[g],wc[g]);end
 end
end endgenerate
wire [7:0] sal;
wire sav,sar,swv,swr,swl,sbv,sbr;
ddr_w_arb arb(.clk(clk),.rst(rst),
 .m0_awid(4'd1),.m0_awaddr(aa[0]),.m0_awlen(al[0]),.m0_awsize(3'd4),.m0_awburst(2'd1),.m0_awlock(1'b0),.m0_awcache(4'd3),.m0_awprot(3'd0),.m0_awvalid(av[0]),.m0_awready(ar[0]),.m0_wdata(wd[0]),.m0_wstrb(ws[0]),.m0_wlast(wl[0]),.m0_wvalid(wv[0]),.m0_wready(wr[0]),.m0_bvalid(bv[0]),.m0_bready(br[0]),
 .m1_awid(4'd4),.m1_awaddr(aa[1]),.m1_awlen(al[1]),.m1_awsize(3'd4),.m1_awburst(2'd1),.m1_awlock(1'b0),.m1_awcache(4'd3),.m1_awprot(3'd0),.m1_awvalid(av[1]),.m1_awready(ar[1]),.m1_wdata(wd[1]),.m1_wstrb(ws[1]),.m1_wlast(wl[1]),.m1_wvalid(wv[1]),.m1_wready(wr[1]),.m1_bvalid(bv[1]),.m1_bready(br[1]),
 .m2_awid(4'd2),.m2_awaddr(aa[2]),.m2_awlen(al[2]),.m2_awsize(3'd4),.m2_awburst(2'd1),.m2_awlock(1'b0),.m2_awcache(4'd3),.m2_awprot(3'd0),.m2_awvalid(av[2]),.m2_awready(ar[2]),.m2_wdata(wd[2]),.m2_wstrb(ws[2]),.m2_wlast(wl[2]),.m2_wvalid(wv[2]),.m2_wready(wr[2]),.m2_bvalid(bv[2]),.m2_bready(br[2]),
 .s_awlen(sal),.s_awvalid(sav),.s_awready(sar),.s_wvalid(swv),.s_wready(swr),.s_wlast(swl),.s_bvalid(sbv),.s_bready(sbr),.s_bid(4'd0),.s_bresp(2'd0));
// Behavioral DDR sink: copies top.v AW hold/staging/count contract; no Pango IP.
// top.v ddr_axi_awlen is four bits, truncating arb_s_awlen before fits/latch.
wire [3:0] dal=sal;
reg holdv=0,ipv=0,bvalid=0;
reg stall_w=0,stall_b=0;
reg [3:0] heldlen;
integer level=0,left=0;
wire fits=(dal < (5'd16-level));
assign sar=sav&&!ipv&&!holdv&&(level==0)&&fits&&!bvalid;
assign swr=(level<16)&&!stall_w;
assign sbv=bvalid&&!stall_b;
wire pop=(left>0);
always @(posedge clk) begin
 if(rst) begin holdv<=0;ipv<=0;bvalid<=0;level<=0;left<=0;end
 else begin
  case ({swv&&swr,pop}) 2'b10:level<=level+1;2'b01:level<=level-1;endcase
  if(sar)begin holdv<=1;heldlen<=dal;end
  if(holdv&&!ipv&&(level>=({1'b0,heldlen}+5'd1))&&(level!=0))begin holdv<=0;ipv<=1;end
  else if(ipv)begin ipv<=0;left<=heldlen+1;end
  if(pop)begin left<=left-1;if(left==1)bvalid<=1;end
  if(sbv&&sbr)bvalid<=0;
 end
end
task automatic cmd(input integer c,input integer bytes);
begin
 @(negedge clk);clen[c]=bytes;cv[c]=1;
 do @(posedge clk); while(!cr[c]);
 @(negedge clk);cv[c]=0;
end endtask
integer i;
initial begin
 for(i=0;i<3;i=i+1)begin clen[i]=0;aborts[i]=0;ac[i]=0;bc[i]=0;wc[i]=0;dc[i]=0;end
 repeat(5)@(negedge clk);rst=0;
 // Healthy control: full burst, single tag, then two bursts with real B replies.
 dv=3'b111;
 cmd(0,256);wait(dc[0]==1);
 cmd(0,16);wait(dc[0]==2);
 cmd(0,512);wait(dc[0]==3);
 repeat(10)@(negedge clk);
 if(ac[0]!=4||bc[0]!=4||wc[0]!=49)$fatal(1,"healthy control failed");
 $display("PASS healthy burst/tag/burst AW=4 B=4 W=49");
 // cam3 holds arbiter with a short camera frame. Other cameras have data.
 dv[2]=0;cmd(2,256);wait(ac[2]==1);
 fork cmd(0,256);cmd(1,256);join
 wait(av[0]&&av[1]);repeat(4)@(negedge clk);
 // Accelerate only watchdog elapsed time, preserving every RTL recovery edge.
 force D[0].dut.wd_cnt=24'hffffff;
 force D[1].dut.wd_cnt=24'hffffff;
 @(negedge clk);release D[0].dut.wd_cnt;release D[1].dut.wd_cnt;
 repeat(6)@(negedge clk);
 if(!av[0]||al[0]!=15||aa[0]!=32'h1000||D[0].dut.len!=16||!D[0].dut.trans||dc[0]!=3||dc[1]!=0||cr[0]||cr[1])$fatal(1,"waiting AW ledger/payload corrupted or false done");
 $display("PASS waiting AW timeout preserves valid/address/len/trans; no false done");
 // Permit 14 zero beats into the stage, then stall with the tail in stream_pipe.
 stall_b=1;
 force D[2].dut.wd_cnt=24'hffffff;
 @(negedge clk);release D[2].dut.wd_cnt;
 wait(wc[2]==14);@(negedge clk);stall_w=1;
 repeat(10)@(negedge clk);
 if(D[2].dut.act_burst_len!=0||!D[2].dut.trans||dc[2]!=0||br[2]||cr[2])$fatal(1,"released before external final W");
 $display("PASS internal act=0 with external W stalled retains transaction and BREADY=0");
 stall_w=0;
 wait(bvalid);repeat(10)@(negedge clk);
 force D[2].dut.wd_cnt=24'hffffff;
 @(negedge clk);release D[2].dut.wd_cnt;
 repeat(10)@(negedge clk);
 if(!D[2].dut.trans||dc[2]!=0||cr[2]||ac[0]!=4||ac[1]!=0)$fatal(1,"released while B withheld");
 $display("PASS external W complete but delayed B keeps owner/trans and no done");
 stall_b=0;
 wait(dc[0]==4&&dc[1]==1&&dc[2]==1);repeat(10)@(negedge clk);
 if(ac[0]!=5||bc[0]!=5||wc[0]!=65||ac[1]!=1||bc[1]!=1||wc[1]!=16||ac[2]!=1||bc[2]!=1||wc[2]!=16||arb.busy||holdv||level!=0)$fatal(1,"recovery ledger mismatch");
 $display("PASS recovered all three cameras AW=5/1/1 B=5/1/1 W=65/16/16 DONE=4/1/1");
 // Abort a longer command: only the already submitted burst is owed to the bus.
 cmd(2,512);wait(ac[2]==2);
 force D[2].dut.wd_cnt=24'hffffff;
 @(negedge clk);release D[2].dut.wd_cnt;
 wait(dc[2]==2);repeat(10)@(negedge clk);
 if(ac[2]!=2||bc[2]!=2||wc[2]!=32||D[2].dut.len!=0||!cr[2])$fatal(1,"unissued remainder not retired after B");
 $display("PASS multi-burst timeout drains accepted burst then retires unissued remainder after B");
 dv[0]=1;cmd(0,16);wait(dc[0]==5);repeat(5)@(negedge clk);
 if(ac[0]!=6||bc[0]!=6||wc[0]!=66)$fatal(1,"post recovery tag failed");
 $display("PASS post-recovery single-beat command");
 if(aborts[0]!=0||aborts[1]!=0||aborts[2]!=2)$fatal(1,"abort attribution wrong");
 $display("PASS separate success/abort: cam1=5/0 cam2=1/0 cam3=0/2");
 $finish;
end
initial begin #100000;$fatal(1,"test timed out");end
endmodule
