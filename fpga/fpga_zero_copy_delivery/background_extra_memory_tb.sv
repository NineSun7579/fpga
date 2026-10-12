`timescale 1ns/1ps
module background_extra_memory_tb;
 localparam W=640,H=480,PIXELS=W*H,OUTPIX=PIXELS/4,BYTES=OUTPIX*2;
 reg clk=0;always #5 clk=!clk;
 reg rst=1,prst=1,enable=1;
 reg [5:0] sof=0,pv=0,pub=0;
 reg [95:0] px=0;reg [191:0] seq=0;
 wire quiet,q,av,wv,wl,br;wire [31:0] wa;wire [7:0] wn;
 wire [127:0] wd;wire [15:0] ws;wire [3071:0] rec;
 reg bv=0;integer cycle=0,left=0,beat=0,wbase=0,bdelay=0,awcount=0,bcount=0;
 integer c,p,bank,slot,lane,i,unit_index,expected,seed,write_words=0,tags=0;
 reg [15:0] memory[0:3145727]; // Six slots of 0x80000 HMIC units each.
 wire war=left==0&&!bv&&cycle%5!=0;
 wire wready=left>0&&cycle%7!=0;
 background_six dut(.clk(clk),.rst(rst),.enable(enable),.invalidate(12'd0),.sof(sof),
 .pixel_valid(pv),.source_bad(6'd0),.raw_publish(pub),.pixels(px),.source_sequence(seq),
 .quiescent(quiet),.quarantine(q),.records(rec),.awaddr(wa),.awlen(wn),.awvalid(av),
 .awready(war),.wdata(wd),.wstrb(ws),.wvalid(wv),.wlast(wl),.wready(wready),
 .bresp(2'd0),.bvalid(bv),.bready(br));
 reg awheld=0,wheld=0;reg [39:0] aws;reg [144:0] wds;
 always @(posedge clk)begin
  cycle<=cycle+1;
  if(!rst)begin
   if(awheld && (!av || {wa,wn}!==aws))$fatal(1,"memory AW stall stability");
   if(wheld && (!wv || {wd,ws,wl}!==wds))$fatal(1,"memory W stall stability");
   awheld<=av&&!war;aws<={wa,wn};wheld<=wv&&!wready;wds<={wd,ws,wl};
   if(av&&war)begin
    left=wn+1;beat=0;wbase=wa-32'h0a200000;awcount=awcount+1;
    if(wbase<0 || wbase>=3145728)$fatal(1,"outside memory");
   end
   if(wv&&wready)begin
    if(wl!=(left==1))$fatal(1,"memory WLAST");
    for(lane=0;lane<8;lane=lane+1)begin
     if(ws[lane*2+:2]!=3)$fatal(1,"memory strobe");
     memory[wbase+beat*8+lane]=wd[lane*16+:16];write_words=write_words+1;
    end
    if(wbase%262144==153600)tags=tags+1;
    left=left-1;beat=beat+1;if(left==0)bdelay=5;
   end
   if(bdelay>0)begin bdelay=bdelay-1;if(bdelay==0)bv<=1;end
   if(bv&&br)begin bv<=0;bcount=bcount+1;end
  end
 end
 // Production PCIe read engine, using the same HMIC unit-addressed memory.
 reg [31:0] base=0,bytes=0;reg start=0,capacity=0;
 wire [31:0] ra;wire [3:0] rn,rid;wire [2:0] size;wire [1:0] burst;
 wire rav,rr;reg active=0;integer rleft=0,rbeat=0,rbase=0;
 wire rar=!active&&cycle%3!=0;
 wire rv=active&&cycle%4!=0;
 reg [127:0] rd;
 always @*begin
  rd=0;
  for(integer k=0;k<8;k=k+1)if(active)rd[k*16+:16]=memory[rbase+rbeat*8+k];
 end
 pcie_fifo engine(.button_rst_n(!prst),.axi_clk(clk),.axi_rst(prst),
 .axi_araddr(ra),.axi_arlen(rn),.axi_arid(rid),.axi_arsize(size),.axi_arburst(burst),
 .axi_arvalid(rav),.axi_arready(rar),.axi_rdata(rd),.axi_rvalid(rv),.axi_rlast(rleft==1),
 .axi_rresp(2'd0),.axi_rid(4'd0),.axi_rready(rr),.axi_awready(1'b0),.axi_wready(1'b0),
 .axi_bid(4'd0),.axi_bresp(2'd0),.axi_bvalid(1'b0));
 integer received=0,enqueued=0,addresses=0,reads=0,read_camera=0,read_bank=0;
 integer arstall=0,rstall=0,capstall=0;
 reg [31:0] nextaddr;
 reg arheld=0;reg [35:0] ars;
 function [127:0] golden(input integer index);
 integer k,pix,coord;reg [127:0] result;
 begin
  result=0;
  if(index==9600)result={96'd0,32'(read_bank+1)};
  else for(k=0;k<8;k=k+1)begin
   pix=index*8+k;coord=(pix/320)*1280+(pix%320)*2;
   result[k*16+:16]=16'(read_camera*1000+read_bank*20000+coord);
  end
  golden=result;
 end endfunction
 always @(posedge clk)if(!prst)begin
  if(arheld && (!rav || {ra,rn}!==ars))$fatal(1,"PCIe AR stall stability");
  arheld<=rav&&!rar;ars<={ra,rn};
  if(rav&&!rar)arstall=arstall+1;
  if(active&&!rv)rstall=rstall+1;
  if(capacity&&engine.read_started)capstall=capstall+1;
  if(rav&&rar)begin
   if(ra!==nextaddr || size!=4 || burst!=1 || rn!=(received==9600?0:15))
    $fatal(1,"PCIe actual AR address/length expected=%h actual=%h",nextaddr,ra);
   nextaddr=nextaddr+16*(rn+1);rbase=ra-32'h0a200000;rleft=rn+1;rbeat=0;active<=1;addresses=addresses+1;
  end
  if(rv&&rr)begin
   if(rd!==golden(received))$fatal(1,"shared memory CPU parity camera=%0d bank=%0d beat=%0d actual=%h expected=%h",read_camera,read_bank,received,rd,golden(received));
   received=received+1;rleft=rleft-1;rbeat=rbeat+1;if(rleft==0)active<=0;
  end
  if(engine.fifo_tx_wr_en)begin
   if(engine.fifo_tx_wr_data!==golden(enqueued))$fatal(1,"PCIe TX FIFO parity beat=%0d",enqueued);
   enqueued=enqueued+1;
  end
 end
 always @(negedge clk)capacity=cycle%37>=30;
 task tick;@(negedge clk);endtask
 task read_bank_payload(input integer camera,input integer bnk);
 integer watchdog;
 begin
  read_camera=camera;read_bank=bnk;slot=camera==5?0:(camera<5?camera:5);
  base=32'h0a200000+slot*32'h80000+bnk*32'h40000;bytes=153616;
  if(rec[(camera-1)*512+bnk*256+:32]!==32'd6 ||
     rec[(camera-1)*512+bnk*256+96+:32]!==base ||
     rec[(camera-1)*512+bnk*256+128+:32]!==32'(bnk+1) ||
     rec[(camera-1)*512+bnk*256+160+:32]!==32'd153600 ||
     rec[(camera-1)*512+bnk*256+192+:32]!==32'h00f00140 ||
     rec[(camera-1)*512+bnk*256+224+:32]!==base+153600)
   $fatal(1,"memory metadata disagrees with payload/tag golden");
  prst=1;start=0;repeat(5)tick();active=0;arheld=0;
  received=0;enqueued=0;addresses=0;nextaddr=base;prst=0;repeat(5)tick();start=1;
  watchdog=0;
  while(enqueued<9601 && watchdog<200000)begin tick();watchdog=watchdog+1;end
  repeat(10)tick();
  if(received!=9601 || enqueued!=9601 || addresses!=601 || engine.r_state!=0 || engine.read_beats_remain!=0)
   $fatal(1,"PCIe read ledger");
  reads=reads+1;
  $display("EXTRA_MEMORY_READ_PASS camera=%0d bank=%0d bytes=153616 beats=%0d AR=%0d FIFO=%0d tag=%0d",camera,bnk,received,addresses,enqueued,bnk+1);
 end endtask
 initial begin
  force engine.fifo_pcie_clk=clk;force engine.fifo_pcie_rst=prst;
  force engine.fpga_ddr3_addr=base;force engine.fpga_ddr3_length=bytes;
  force engine.fpga_ddr3_total_length=bytes;force engine.mwr_tx_busy=start;
  force engine.mrd_rx_busy=0;force engine.fpga_tx_clk_en=0;force engine.fpga_rx_clk_en=0;
  force engine.fifo_rx_empty=1;force engine.fifo_rx_water_level=0;
  force engine.fifo_tx_almost_full=capacity;force engine.fifo_tx_empty=1;force engine.fifo_tx_water_level=0;
  for(i=0;i<3145728;i=i+1)memory[i]=16'hdead;
  repeat(5)tick();rst=0;
  for(bank=0;bank<2;bank=bank+1)begin
   sof=6'h3f;tick();sof=0;
   for(p=0;p<PIXELS;p=p+1)begin
    pv=6'h3f;for(c=0;c<6;c=c+1)px[c*16+:16]=(c+1)*1000+bank*20000+p;tick();
   end
   pv=0;repeat(64)tick();
   for(c=0;c<6;c=c+1)begin
    if(rec[c*512+bank*256+:2]==2)$fatal(1,"premature RAW barrier publication");
    seq[c*32+:32]=bank+1;
   end
   pub=6'h3f;tick();pub=0;wait(quiet);repeat(10)tick();
   for(c=0;c<6;c=c+1)if(rec[c*512+bank*256+:2]!=2)$fatal(1,"record not valid");
  end
  enable=0;
  // Every inter-burst gap remains poison. Check all 600 gaps in all 12 banks.
  for(slot=0;slot<6;slot=slot+1)for(bank=0;bank<2;bank=bank+1)
   for(i=0;i<600;i=i+1)for(lane=128;lane<256;lane=lane+1)
    if(memory[slot*524288+bank*262144+i*256+lane]!==16'hdead)$fatal(1,"HMIC gap overwritten");
  for(c=1;c<=6;c=c+1)for(bank=0;bank<2;bank=bank+1)read_bank_payload(c,bank);
  if(awcount!=7212 || bcount!=awcount || tags!=12 || reads!=12 || !quiet || q || arstall==0 || rstall==0 || capstall==0)
   $fatal(1,"memory final ledgers AW=%0d B=%0d tags=%0d reads=%0d",awcount,bcount,tags,reads);
  $display("EXTRA_MEMORY_PASS reads=%0d AW=%0d B=%0d tags=%0d words=%0d poison_gap_units=921600 ARstall=%0d Rstall=%0d capacitystall=%0d",reads,awcount,bcount,tags,write_words,arstall,rstall,capstall);$finish;
 end
 initial begin #15000000;$fatal(1,"memory timeout");end
endmodule
