`timescale 1ns/1ps
module review_writer_case #(parameter ID=1)(output reg finished=0,output integer errors=0);
reg clk=0,rst=1,cmd_valid=0,fault_in=0,dvalid=0,awr=0,wr=0,bv=0;
always #5 clk=~clk;
reg [31:0] cmd_len=512;
wire cr,dr,done,ab,av,wv,wl,br;
wire [31:0] aa; wire [7:0] al; wire [3:0] aid;
wire [127:0] wd; wire [15:0] ws;
reg [127:0] din=128'h12345678;
reg [15:0] available=32;
wire abort_req;wire [3:0] broadcast_abort;
assign abort_req=broadcast_abort[0];

reg cold_req=0;
always @(negedge clk) cold_req<=!rst;
wire session_fault,supervisor_cold;
four_camera_reset_supervisor #(.CLOCK_LIMIT(10000)) supervisor(
 .clk(clk),.epoch_reset(rst),.cold_request(cold_req),.source_clk({4{clk}}),
 .i2c_start_en(4'hf),.cam_init_done(4'hf),.ov_rst_n(4'hf),.video_reset(rst),
 .boundary_fault({3'd0,fault_in}),.capture_abort_req(4'd0),.writer_abort(4'd0),
 .camera_session_fault(session_fault),.transport_abort(broadcast_abort),.cold_system_reset(supervisor_cold));


axi_dma_write_tc04 #(.WAIT_FOR_DATA(1),.WD_LIMIT(24'd1000),.BURST_LEN(16)) dut(
 .clk(clk),.rst(rst),.cmd_valid(cmd_valid),.cmd_ready(cr),.cmd_addr(32'h800000),.cmd_len(cmd_len),.cmd_id(4'(ID)),
 .data_in_available(available),.abort_req(abort_req),.data_in_abort(ab),.data_in(din),.data_in_keep(16'hffff),
 .data_in_valid(dvalid),.data_in_last(done),.data_in_ready(dr),
 .m_axi_awid(aid),.m_axi_awaddr(aa),.m_axi_awlen(al),.m_axi_awvalid(av),.m_axi_awready(awr),
 .m_axi_wdata(wd),.m_axi_wstrb(ws),.m_axi_wlast(wl),.m_axi_wvalid(wv),.m_axi_wready(wr),
 .m_axi_bid(4'(ID)),.m_axi_bresp(2'b00),.m_axi_bvalid(bv),.m_axi_bready(br));
integer aw_count,w_count,b_count,ab_count,done_count,owed,expected,which,zero_count;
reg awstall,wstall; reg [43:0] awheld; reg [144:0] wheld;
task check(input bit ok,input string msg);
 if(!ok) begin errors++; $display("FAIL ledger id=%0d cut=%0d %s",ID,which,msg); end
endtask
always @(posedge clk) begin
 if(rst) begin
  aw_count=0;w_count=0;b_count=0;ab_count=0;done_count=0;owed=0;expected=0;zero_count=0;awstall=0;wstall=0;
 end else begin
  if(awstall) check(av && {aid,aa,al}===awheld,"AW withdrawn/changed under backpressure");
  if(wstall) check(wv && {wd,ws,wl}===wheld,"W withdrawn/changed under backpressure");
  awstall=av&&!awr; awheld={aid,aa,al}; wstall=wv&&!wr; wheld={wd,ws,wl};
  if(av&&awr) begin check(owed==0,"overlapping burst"); aw_count++; owed=al+1; expected+=al+1; end
  if(wv&&wr) begin check(owed>0,"W without AW credit"); check(wl==(owed==1),"WLAST mismatch"); owed--; w_count++; if(ws==0) zero_count++; end
  if(br) check(owed==0 && aw_count>b_count,"BREADY before external WLAST or no AW");
  if(bv&&br) b_count++;
  if(ab) begin check(owed==0 && aw_count==b_count,"abort acknowledged with external debt"); ab_count++; end
  if(done) begin check(owed==0 && aw_count==b_count,"success before B"); done_count++; end
 end
end
task tick; @(negedge clk); endtask
task reset_case;
 rst=1;cmd_valid=0;fault_in=0;dvalid=0;available=32;awr=0;wr=0;bv=0;
 repeat(5) tick();rst=0;repeat(40) tick();
endtask
task command;
 cmd_valid=1; @(posedge clk); while(!cr) @(posedge clk); tick();cmd_valid=0;
endtask
task fault;
 fault_in=1;dvalid=0;available=0;
endtask
initial begin
 for(which=0;which<8;which++) begin
  reset_case();
  if(which==0) begin command(); fault(); end
  else begin
   dvalid=1;command(); wait(av);tick();
   if(which==1) begin fault();repeat(12) tick();check(av,"AW not preserved");end
   awr=1;wait(aw_count==1);tick();awr=0;
   if(which==2) fault();
   if(which==3) begin wait(wv);tick();repeat(4) tick();fault();repeat(9) tick();end
   wr=1;
   if(which==4) begin wait(w_count==3);tick();fault();end
   if(which==5) begin wait(w_count==15);tick();wr=0;wait(wv&&wl);repeat(5) tick();fault();repeat(9) tick();wr=1;end
   wait(w_count==16);tick();wr=0;
   if(which==6) fault();
   repeat(1100) tick();check(ab_count==0&&done_count==0,"completion fabricated before delayed B beyond WD_LIMIT");
   if(which==7) fault();
   bv=1;wait(b_count==1);tick();bv=0;
  end
  repeat(20) tick();
  check(ab_count==1 && done_count==0,"abort must produce exactly one failure and no success");
  check(aw_count==b_count && w_count==expected && owed==0,"unretired ledger");
  check(aw_count==(which==0?0:1),"new AW after sticky abort");
  $display("REVIEW_LEDGER id=%0d cut=%0d AW=%0d W=%0d B=%0d zero_strobe=%0d abort=%0d errors=%0d",ID,which,aw_count,w_count,b_count,zero_count,ab_count,errors);
 end
 finished=1;
end
endmodule
module tb_ledger;
wire [3:0] finished; wire [31:0] e0,e1,e2,e3;
review_writer_case #(1) c1(finished[0],e0);
review_writer_case #(4) c2(finished[1],e1);
review_writer_case #(2) c3(finished[2],e2);
review_writer_case #(8) c4(finished[3],e3);
initial begin wait(&finished);$display("REVIEW_LEDGER_DONE errors=%0d",e0+e1+e2+e3);$finish;end
initial begin #200000; $display("FAIL ledger timeout");$finish;end
endmodule
