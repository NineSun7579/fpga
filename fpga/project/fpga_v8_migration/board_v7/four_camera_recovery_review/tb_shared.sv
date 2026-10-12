`timescale 1ns/1ps
module tb_shared;
reg clk=0,rst=1;
always #5 clk=~clk;
GTP_GRS GRS_INST(.GRS_N(1'b1));
reg [3:0] cmd=0,fault=0;
wire [3:0] cr,done,ab;
wire [6:0] av,ar,wv,wr,wl,bv,br;
wire [27:0] aid,bid,ac;
wire [223:0] aa;
wire [55:0] al;
wire [20:0] asz,ap;
wire [13:0] burst,bresp;
wire [6:0] lock;
wire [895:0] wd;
wire [111:0] ws;
genvar i;
generate for(i=0;i<4;i++) begin: cams
 localparam ID=(i==0?1:i==1?4:i==2?2:8);
 axi_dma_write_tc04 #(.WAIT_FOR_DATA(1),.BURST_LEN(16),.WD_LIMIT(24'd100)) writer(
  .clk(clk),.rst(rst),.cmd_valid(cmd[i]),.cmd_ready(cr[i]),.cmd_addr(32'h800000+i*4096),.cmd_len(32'd256),.cmd_id(4'(ID)),
  .data_in_available(fault[i]?16'd0:16'd16),.abort_req(fault[i]),.data_in_abort(ab[i]),
  .data_in(128'(ID)),.data_in_keep(16'hffff),.data_in_valid(!fault[i]),.data_in_last(done[i]),
  .m_axi_awid(aid[i*4+:4]),.m_axi_awaddr(aa[i*32+:32]),.m_axi_awlen(al[i*8+:8]),
  .m_axi_awsize(asz[i*3+:3]),.m_axi_awburst(burst[i*2+:2]),.m_axi_awlock(lock[i]),.m_axi_awcache(ac[i*4+:4]),.m_axi_awprot(ap[i*3+:3]),
  .m_axi_awvalid(av[i]),.m_axi_awready(ar[i]),.m_axi_wdata(wd[i*128+:128]),.m_axi_wstrb(ws[i*16+:16]),
  .m_axi_wlast(wl[i]),.m_axi_wvalid(wv[i]),.m_axi_wready(wr[i]),.m_axi_bid(bid[i*4+:4]),
  .m_axi_bresp(bresp[i*2+:2]),.m_axi_bvalid(bv[i]),.m_axi_bready(br[i]));
end endgenerate
assign av[6:4]=0;assign aid[27:16]=0;assign aa[223:128]=0;assign al[55:32]=0;
assign asz[20:12]=0;assign burst[13:8]=0;assign lock[6:4]=0;assign ac[27:16]=0;assign ap[20:12]=0;
assign wd[895:512]=0;assign ws[111:64]=0;assign wl[6:4]=0;assign wv[6:4]=0;assign br[6:4]=0;
wire sav,sar,swv,swr,swl,sbv,sbr;
wire [3:0] said,sbid;wire [31:0] saa;wire [7:0] sal;wire [2:0] sas;wire [1:0] sab,sresp;
wire [127:0] swd;wire [15:0] sws;
wire busy,arb_error;wire [2:0] owner;
fpga_v8_ddr_write_arbiter arb(.clk(clk),.rst_n(!rst),
 .m_awid(aid),.m_awaddr(aa),.m_awlen(al),.m_awsize(asz),.m_awburst(burst),.m_awlock(lock),.m_awcache(ac),.m_awprot(ap),
 .m_awqos(28'd0),.m_awregion(28'd0),.m_awvalid(av),.m_awready(ar),.m_wdata(wd),.m_wstrb(ws),.m_wlast(wl),.m_wvalid(wv),.m_wready(wr),
 .m_bid(bid),.m_bresp(bresp),.m_bvalid(bv),.m_bready(br),
 .s_awid(said),.s_awaddr(saa),.s_awlen(sal),.s_awsize(sas),.s_awburst(sab),.s_awvalid(sav),.s_awready(sar),
 .s_wdata(swd),.s_wstrb(sws),.s_wlast(swl),.s_wvalid(swv),.s_wready(swr),
 .s_bid(sbid),.s_bresp(sresp),.s_bvalid(sbv),.s_bready(sbr),.busy(busy),.owner(owner),.error(arb_error));
wire vav;reg vawr=0,vwr=0,vlast=0;reg [3:0] vid=0;
wire [3:0] vaid,val;wire [27:0] vaa;wire [127:0] vdata;wire [15:0] vstrb;wire [7:0] adapter_errors;
fpga_v8_ddr_adapter_tc03 adapter(.clk(clk),.rst_n(!rst),
 .s_awid(said),.s_awaddr(saa),.s_awlen(sal),.s_awsize(sas),.s_awburst(sab),.s_awvalid(sav),.s_awready(sar),
 .s_wdata(swd),.s_wstrb(sws),.s_wlast(swl),.s_wvalid(swv),.s_wready(swr),.s_bid(sbid),.s_bresp(sresp),.s_bvalid(sbv),.s_bready(sbr),
 .s_arid(7'd0),.s_araddr(32'd0),.s_arlen(8'd0),.s_arsize(3'd4),.s_arburst(2'd1),.s_arvalid(1'b0),.s_rready(1'b0),
 .v_awid(vaid),.v_awaddr(vaa),.v_awlen(val),.v_awvalid(vav),.v_awready(vawr),.v_wdata(vdata),.v_wstrb(vstrb),
 .v_wready(vwr),.v_wlast(vlast),.v_wid(vid),.v_arready(1'b0),.v_rid(4'd0),.v_rdata(128'd0),.v_rlast(1'b0),.v_rvalid(1'b0),.error_flags(adapter_errors));
integer errors=0,which,j,k,aw_count,w_count,b_count,v_count,zero_count,owed;
integer successes[0:3],failures[0:3];
reg astall,wstall;reg [43:0] ahold;reg [144:0] whold;
task check(input bit ok,input string msg);
 if(!ok) begin errors++;$display("FAIL shared case=%0d %s",which,msg);end
endtask
always @(posedge clk) begin
 if(rst) begin
  aw_count=0;w_count=0;b_count=0;v_count=0;zero_count=0;owed=0;astall=0;wstall=0;
  for(integer n=0;n<4;n++) begin successes[n]=0;failures[n]=0;end
 end else begin
  if(astall) check(sav&&{said,saa,sal}===ahold,"shared AW stability");
  if(wstall) check(swv&&{swd,sws,swl}===whold,"shared W stability");
  astall=sav&&!sar;ahold={said,saa,sal};wstall=swv&&!swr;whold={swd,sws,swl};
  if(sav&&sar) begin check(owed==0,"shared overlapping AW");aw_count++;owed=sal+1;end
  if(swv&&swr) begin check(owed>0&&swl==(owed==1),"shared W ledger");owed--;w_count++;end
  if(sbv&&sbr) begin check(owed==0,"shared early B");b_count++;end
  if(vwr) begin v_count++;if(vstrb==0)zero_count++;end
  for(integer n=0;n<4;n++) begin
   if(done[n]) successes[n]++;
   if(ab[n]) failures[n]++;
  end
 end
end
task tick; @(negedge clk);endtask
initial begin
 for(which=0;which<2;which++) begin
  rst=1;cmd=0;fault=0;vawr=0;vwr=0;vlast=0;
  repeat(20)tick();rst=0;repeat(10)tick();cmd=15;
  @(posedge clk);check(cr==15,"all four command ready");tick();cmd=0;
  wait(w_count==3);tick();fault=(which==0?4'b0001:4'b1111);
  for(j=0;j<4;j++) begin
   wait(vav);tick();vid=vaid;check(val==15,"production 16 beat burst");
   // Vendor AW is held. Real adapter has buffered all W, but no B exists.
   repeat(15)tick();vawr=1;tick();vawr=0;
   for(k=0;k<16;k++) begin
    if(k==15) begin
     repeat(150)tick();
     check(b_count==j && aw_count==j+1 && busy,"delayed vendor last must retain shared owner beyond WD_LIMIT");
     check((j!=0)||((successes[0]+failures[0])==0),"no fabricated first completion");
    end
    vwr=1;vlast=(k==15);tick();vwr=0;vlast=0;
    if(k%3==0) repeat(3)tick();
   end
   wait(b_count==j+1);tick();
  end
  repeat(25)tick();
  check(aw_count==4&&w_count==64&&b_count==4&&v_count==64,"four camera ledger totals");
  check(!busy&&!arb_error&&adapter_errors==0,"shared fabric retained error/owner");
  for(k=0;k<4;k++) check(failures[k]==((which==1||k==0)?1:0) && successes[k]==((which==0&&k!=0)?1:0),"per-camera result routing");
  $display("REVIEW_SHARED case=%0d AW=%0d W=%0d vendorW=%0d B=%0d zero_strobe=%0d busy=%b errors=%0d",which,aw_count,w_count,v_count,b_count,zero_count,busy,errors);
 end
 $display("REVIEW_SHARED_DONE errors=%0d",errors);$finish;
end
initial begin #200000;$display("FAIL shared timeout");$finish;end
endmodule
