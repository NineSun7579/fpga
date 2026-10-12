`timescale 1ns/1ps
module background_extra_fault_tb #(parameter CASE=0);
 reg clk=0;always #5 clk=!clk;
 reg rst=1,sof=0,pv=0,bad=0,pub=0;
 reg [15:0] px=0;reg [31:0] seq=0;
 wire quiet,q,av,wv,wl,br;wire [31:0] addr;wire [7:0] len;
 wire [127:0] wd;wire [15:0] ws;wire [3071:0] rec;
 reg ar=1,wr=1,bv=0,holdb=0;
 integer left=0,beat=0,aw=0,b=0,p,stage=CASE%4,delayb=0,k,index,expected;
 reg current_tag;
 reg pending=0,awhold=0,whold=0,acceptw;
 reg [39:0] asave;reg [144:0] wsave;
 background_six #(.WIDTH(32),.HEIGHT(16),.DEADLINE(CASE>=4?800:100000)) dut(
 .clk(clk),.rst(rst),.enable(1'b1),.invalidate(12'd0),.sof({5'd0,sof}),
 .pixel_valid({5'd0,pv}),.source_bad({5'd0,bad}),.raw_publish({5'd0,pub}),
 .pixels({80'd0,px}),.source_sequence({160'd0,seq}),.quiescent(quiet),.quarantine(q),.records(rec),
 .awaddr(addr),.awlen(len),.awvalid(av),.awready(ar),.wdata(wd),.wstrb(ws),
 .wvalid(wv),.wlast(wl),.wready(wr && left>0),.bresp(2'd0),.bvalid(bv&&!holdb),.bready(br));
 always @(posedge clk)if(!rst)begin
  acceptw=wv&&wr&&left>0;
  if(awhold && (!av || {addr,len}!==asave))$fatal(1,"AW unstable through fault");
  if(whold && (!wv || {wd,ws,wl}!==wsave))$fatal(1,"W unstable through fault");
  awhold<=av&&!ar;asave<={addr,len};
  whold<=wv&&!(wr&&left>0);wsave<={wd,ws,wl};
  if(av&&ar)begin
   if(pending || left!=0)$fatal(1,"overlap AW");
   pending=1;left=len+1;beat=0;aw=aw+1;
   current_tag=addr==32'h0a280100;
   if(len!=(current_tag?0:15))$fatal(1,"fault AWLEN");
   if(rec[1:0]!=1)$fatal(1,"guard before AW");
  end
  if(acceptw)begin
   if(wl!=(left==1) || ws!=16'hffff)$fatal(1,"WLAST/strobe ledger");
   if(current_tag)begin if(wd!==128'd1)$fatal(1,"fault tag data");end
   else for(k=0;k<8;k=k+1)begin
    index=beat*8+k;expected=16'h1234+(index/16)*64+(index%16)*2;
    if(wd[k*16+:16]!==16'(expected))$fatal(1,"fault drained data pixel=%0d",index);
   end
   left=left-1;beat=beat+1;if(left==0)delayb=3;
  end
  if(delayb>0)begin delayb=delayb-1;if(delayb==0)bv<=1;end
  if(bv&&br&&!holdb)begin bv<=0;pending=0;b=b+1;end
  if(pending && quiet)$fatal(1,"quiescent before B");
 end
 // Keep B hidden from DUT during the selected delayed response.
 // The bvalid signal itself is driven only after holdb clears.
 task tick;@(negedge clk);endtask
 initial begin
  repeat(5)tick();rst=0;
  if(stage==0)begin ar=0;wr=0;end
  sof=1;tick();sof=0;
  fork
   begin for(p=0;p<512;p=p+1)begin pv=1;px=p+16'h1234;tick();end pv=0;
    seq=1;pub=1;tick();pub=0;
   end
   begin
    case(stage)
     0:wait(av);
     1:begin wait(beat==5);tick();wr=0;wait(wv);end
     2:begin wait(beat==15);tick();wr=0;wait(wv&&wl);end
     3:begin wait(addr==32'h0a280100 && av);tick();holdb=1;end
    endcase
    if(stage==3)begin wait(left==0 && pending);tick();end
    if(CASE<4)begin tick();bad=1;tick();bad=0;end
    else wait(dut.cameras[0].producer.failed);
    repeat(20)tick();
    if(quiet || rec[1:0]!=1)$fatal(1,"fault prematurely invalidated or quiesced announced transaction");
    ar=1;wr=1;holdb=0;
   end
  join
  wait(quiet);repeat(5)tick();
  if(rec[1:0]!=0 || aw!=b || q)$fatal(1,"fault final ledger/validity guard=%d AW=%d B=%d q=%d",rec[1:0],aw,b,q);
  $display("EXTRA_FAULT_PASS case=%0d cause=%0d stage=%0d AW=%0d B=%0d",CASE,CASE/4,stage,aw,b);$finish;
 end
 initial begin #200000;$fatal(1,"fault timeout case=%0d",CASE);end
endmodule

module background_extra_fifo_tb;
 reg clk=0;always #5 clk=!clk;
 reg rst=1,sof=0,pv=0,take=0,grant=0,retire=0;
 reg [15:0] px=0;
 wire idle;wire [511:0] rec;
 background_producer #(.WIDTH(640),.HEIGHT(4),.DEPTH(16),.DEADLINE(10000)) dut(
 .clk(clk),.rst(rst),.enable(1'b1),.quarantine(1'b0),.invalidate(2'd0),.sof(sof),
 .pixel_valid(pv),.source_bad(1'b0),.raw_publish(1'b0),.pixel(px),.source_sequence(32'd0),
 .grant(grant),.take(take),.retire(retire),.retire_bad(1'b0),.idle(idle),.records(rec));
 task tick;@(negedge clk);endtask
 integer i;
 initial begin
  repeat(4)tick();rst=0;sof=1;tick();sof=0;
  for(i=0;i<256;i=i+1)begin pv=1;px=i;tick();end pv=0;
  if(dut.count!=16)$fatal(1,"FIFO not full");
  grant=1;tick();grant=0;
  for(i=256;i<270;i=i+1)begin pv=1;px=i;tick();end
  take=1;px=270;#1;
  if(!dut.push || !dut.pop || dut.overflow)$fatal(1,"full simultaneous event not reached");
  tick();take=0;
  if(dut.count!=16 || dut.failed || dut.fifo[15][127:112]!=254 || dut.fifo[0][15:0]!=256)
   $fatal(1,"full push/pop lost data/count");
  for(i=271;i<287;i=i+1)begin px=i;tick();end pv=0;
  if(!dut.failed || idle || rec[1:0]!=1)$fatal(1,"overflow must wait for announced retirement");
  retire=1;tick();retire=0;tick();
  if(!idle || rec[1:0]!=0 || dut.count!=0)$fatal(1,"overflow retirement did not invalidate");
  $display("EXTRA_FIFO_PASS full_push_pop=1 full_push_without_pop=1");$finish;
 end
endmodule
