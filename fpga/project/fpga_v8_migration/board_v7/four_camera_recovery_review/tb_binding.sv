`timescale 1ns/1ps
module tb_binding;
reg clk=0,cam=0,rst=1,local_req=0,sv=0,pvalid=0;
always #5 clk=~clk;
always #6 cam=~cam;
reg [15:0] pixel=0;
wire fault;
GTP_GRS GRS_INST(.GRS_N(1'b1));
// Actual sticky fault source; source pixels below enter at the DDR wrapper boundary.
cdc_recovery boundary(.system_reset(rst),.cam_clk(cam),.cam_rst(rst),.video_clk(clk),
 .video_rst(rst|local_req),.s_data(16'b0),.s_valid(1'b0),.s_hsync(1'b0),.s_vsync(1'b0),.boundary_fault(fault));
wire abort_req,ab,done,cv,cr,dv,dr;
wire [15:0] available;
wire [127:0] data;
wire [31:0] ca,cl;
wire [1:0] req;
ddr_recovery #(.CAM_DATA_LEN(32)) ddr(.axi_clk(clk),.axi_rst(rst),
 .transport_abort(fault),.dma_abort(ab),.dma_abort_req(abort_req),.dma_done(done),.axi_cam_en(1'b1),
 .cam_data_addr_1(32'h800000),.cam_data_addr_2(32'ha00000),.cam_data_len(6'd32),
 .s_data(pixel),.s_data_valid(pvalid),.s_hsync(pvalid),.s_vsync(sv),
 .axi_data(data),.axi_data_valid(dv),.axi_data_ready(dr),.axi_data_available(available),
 .axi_cmd_addr(ca),.axi_cmd_len(cl),.axi_cmd_valid(cv),.axi_cmd_ready(cr),.xdma_req(req),.xdma_ack(2'b11));
reg awr=0,wr=0,bv=0;
wire av,wv,wl,br; wire [31:0] aa; wire [7:0] al; wire [127:0] wd;wire [15:0] ws;
axi_dma_write_tc04 #(.WAIT_FOR_DATA(1),.BURST_LEN(16),.WD_LIMIT(24'd1000)) writer(
 .clk(clk),.rst(rst),.cmd_valid(cv),.cmd_ready(cr),.cmd_addr(ca),.cmd_len(cl),.cmd_id(4'd1),
 .data_in_available(available),.abort_req(abort_req),.data_in_abort(ab),.data_in(data),.data_in_keep(16'hffff),
 .data_in_valid(dv),.data_in_last(done),.data_in_ready(dr),
 .m_axi_awaddr(aa),.m_axi_awlen(al),.m_axi_awvalid(av),.m_axi_awready(awr),
 .m_axi_wdata(wd),.m_axi_wstrb(ws),.m_axi_wlast(wl),.m_axi_wvalid(wv),.m_axi_wready(wr),
 .m_axi_bid(4'd1),.m_axi_bresp(2'b00),.m_axi_bvalid(bv),.m_axi_bready(br));
integer errors=0,which,aw_count,w_count,b_count,ab_count,done_count,publish_count,owed,expected;
reg awstall,wstall;reg [39:0] awheld;reg [144:0] wheld;
task check(input bit ok,input string msg);
 if(!ok) begin errors++;$display("FAIL binding cut=%0d %s t=%0t",which,msg,$time);end
endtask
always @(posedge clk) begin
 if(rst) begin
  aw_count=0;w_count=0;b_count=0;ab_count=0;done_count=0;publish_count=0;owed=0;expected=0;awstall=0;wstall=0;
 end else begin
  if(awstall) check(av&&{aa,al}===awheld,"AW stall stability");
  if(wstall) check(wv&&{wd,ws,wl}===wheld,"W stall stability");
  awstall=av&&!awr;awheld={aa,al};wstall=wv&&!wr;wheld={wd,ws,wl};
  if(av&&awr) begin check(owed==0,"AW overlap");aw_count++;owed=al+1;expected+=al+1;end
  if(wv&&wr) begin check(owed>0,"W without AW");check(wl==(owed==1),"WLAST");owed--;w_count++;end
  if(br) check(owed==0&&aw_count>b_count,"BREADY ledger");
  if(bv&&br) b_count++;
  if(ab) begin check(owed==0&&aw_count==b_count,"early abort ack");ab_count++;end
  if(done) done_count++;
  if(ddr.ov5640_ddr_w_ctrl.publish) begin check(!fault,"publish under fault");publish_count++;end
 end
end
task tick; @(negedge clk); endtask
task inject;
 local_req=1; tick();local_req=0;check(fault,"fault must stay sticky");
endtask
task send_b;
 repeat(13) tick();bv=1;@(posedge clk);while(!br) @(posedge clk);tick();bv=0;
endtask
task pixels;
 integer k;
 sv=1;repeat(6) tick();sv=0;repeat(12) tick();
 for(k=0;k<256;k++) begin pvalid=1;pixel=k;tick();end
 pvalid=0;
endtask
initial begin
 for(which=0;which<11;which++) begin
  rst=1;local_req=0;sv=0;pvalid=0;awr=0;wr=0;bv=0;
  repeat(30) tick();rst=0;repeat(30) tick();
  fork
   pixels();
   begin
    if(which==0) begin wait(cv&&cr);tick();inject();repeat(40) tick();end
    else begin
     wait(av);tick();
     if(which==1) begin inject();repeat(10) tick();end
     awr=1;wait(aw_count==1);tick();awr=0;
     if(which==2) inject();
     if(which==3) begin wait(wv);repeat(7) tick();inject();repeat(8) tick();end
     wr=1;
     if(which==4) begin wait(w_count==3);tick();inject();end
     wait(w_count==16);tick();wr=0;
     if(which==5) inject();
     send_b();
     if(which>=6) begin
      // Complete the second data burst naturally to reach the real tag path.
      awr=1;wr=1;wait(w_count==32);tick();send_b();
      awr=0;wr=0;wait(av);tick();check(aa==32'h800200 && al==0,"natural tag AW");
      if(which==6) begin inject();repeat(10) tick();end
      awr=1;wait(aw_count==3);tick();awr=0;
      if(which==7) begin wait(wv&&wl);repeat(8) tick();inject();repeat(8) tick();end
      wr=1;wait(w_count==33);tick();wr=0;
      // which 8 races fault with tag B; DMA success/publication must be suppressed.
      if(which==8) begin local_req=1;bv=1;@(posedge clk);tick();local_req=0;bv=0;end
      else begin
       send_b();
       if(which==10) begin check(done,"natural tag dma_done coincidence");inject();end
      end
     end
    end
   end
  join
  repeat(40) tick();
  if(which<9) begin
   check(fault && abort_req,"fault must be held until global cold reset");
   check(ab_count==1&&publish_count==0,"one real failure, no publication");
  end else if(which==9) begin
   check(!fault && !abort_req,"cold reset clears fault");
   check(ab_count==0&&done_count==2&&publish_count==1,"healthy frame plus tag must publish after cold reset");
  end else begin
   check(fault&&abort_req&&ab_count==0&&done_count==2&&publish_count==0,"idle DMA has no abort ack; same-cycle fault suppresses tag publication");
  end
  check(aw_count==b_count&&owed==0&&w_count==expected,"AXI obligations missing");
  $display("REVIEW_BINDING cut=%0d AW=%0d W=%0d B=%0d abort=%0d data_success=%0d publish=%0d errors=%0d",which,aw_count,w_count,b_count,ab_count,done_count,publish_count,errors);
 end
 $display("REVIEW_BINDING_DONE errors=%0d",errors);$finish;
end
initial begin #500000;$display("FAIL binding timeout cut=%0d AW=%0d W=%0d B=%0d state=%0d avail=%0d fault=%b",which,aw_count,w_count,b_count,ddr.ov5640_ddr_w_ctrl.curr_state,available,fault);$finish;end
endmodule
