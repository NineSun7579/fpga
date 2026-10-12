`timescale 1ns/1ps
module tb_credit_tail;
reg clk=0;always #5 clk=~clk;
reg rst=1,cv=0,abort_req=0;
reg [31:0] ca=0,cl=0;
integer available=0;
wire cr,dr,done,aborted,av,ar,wv,wr,wl,br;
wire [7:0] al;
wire [31:0] aa;
reg bv=0;
reg active=0;
integer leftw=0,awcount=0,bcount=0,success=0,abortcount=0,words=0;
assign ar=!active&&!bv;
assign wr=active;
axi_dma_write #(.WAIT_FOR_DATA(1),.BURST_LEN(16),.WD_LIMIT(24)) dut(
 .clk(clk),.rst(rst),.cmd_valid(cv),.cmd_addr(ca),.cmd_len(cl),.cmd_id(4'd1),.cmd_ready(cr),
 .abort_req(abort_req),.data_in_abort(aborted),.data_in_available(16'(available)),
 .data_in(128'h1234),.data_in_keep(16'hffff),.data_in_valid(available>0),.data_in_ready(dr),.data_in_last(done),
 .m_axi_awaddr(aa),.m_axi_awlen(al),.m_axi_awvalid(av),.m_axi_awready(ar),
 .m_axi_wlast(wl),.m_axi_wvalid(wv),.m_axi_wready(wr),.m_axi_bvalid(bv),.m_axi_bready(br),.m_axi_bid(4'd1),.m_axi_bresp(2'b00));
always @(posedge clk)if(!rst)begin
 if(av&&ar)begin
  if(al+1>available)$fatal(1,"AW without stored credits");
  if((aa%4096)+(al+1)*16>4096)$fatal(1,"4K boundary crossed");
  if(awcount==0&&(aa!=32'hff0||al!=0))$fatal(1,"first boundary split");
  if(awcount==1&&(aa!=32'h1000||al!=4))$fatal(1,"five beat tail");
  awcount=awcount+1;leftw=al+1;active<=1;
 end
 if(wv&&wr)begin
  if(leftw==0||wl!==(leftw==1))$fatal(1,"W obligation mismatch");
  leftw=leftw-1;words=words+1;if(leftw==0)bv<=1;
 end
 if(bv&&br)begin bv<=0;active<=0;bcount=bcount+1;end
 if(done)success=success+1;
 if(aborted)abortcount=abortcount+1;
 if(done&&aborted)$fatal(1,"overlap");
end
always @(posedge clk)if(!rst&&dr&&available>0)available<=available-1;
task command(input [31:0] a,input [31:0] len);
begin @(negedge clk);ca=a;cl=len;cv=1;do @(posedge clk);while(!cr);@(negedge clk);cv=0;end
endtask
initial begin
 repeat(5)@(negedge clk);rst=0;repeat(5)@(negedge clk);
 command('hff0,96);
 repeat(8)@(negedge clk);if(av||active)$fatal(1,"empty source reserved bus");
 #1;available=6;
 wait(success==1);repeat(5)@(negedge clk);
 if(awcount!=2||bcount!=2||words!=6)$fatal(1,"boundary/tail ledger");
 $display("PASS stored-credit 4K split 1+5 beats; partial tail and no early AW");
 command('h2000,256);#1;available=3;
 wait(abortcount==1);repeat(5)@(negedge clk);
 if(awcount!=2||bcount!=2||success!=1||!cr)$fatal(1,"pre-AW starvation retirement");
 $display("PASS partial pre-AW timeout retires locally with no AW/B");
 #1;available=0;command('h3000,16);#1;available=1;
 wait(success==2);repeat(5)@(negedge clk);
 if(awcount!=3||bcount!=3||words!=7)$fatal(1,"recovered single beat");
 $display("PASS CREDIT TAIL recovery AW=3 B=3 W=7 success=2 abort=1");$finish;
end
initial begin #10000;$fatal(1,"timeout");end
endmodule
