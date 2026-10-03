// Isolated candidate: raw byte/K input, BC/28 controls and prefix-pair deletion.
// Not a general GE PCS decoder. Unknown K/fragments set sticky malformed.
module rx_symbol_candidate #(parameter FIFO_AW=11)(
 input i_clk,i_rst_n,i_en,input [31:0] i_rxd,input [3:0] i_rxk,
 output reg o_vs,o_hs,o_de,output reg [15:0] o_pix,output o_overflow,output o_malformed);
 reg [95:0] buf_d,next_d; reg [11:0] buf_k,next_k;
 integer count,next_count,cursor,available,events,step;
 reg shadow_vs,shadow_hs,next_vs,next_hs,bad,next_bad,acquired,next_acquired;
 assign o_malformed=bad;
 reg [18:0] event0,event1,ev; reg valid_ev;
 reg [18:0] mem0[0:(1<<(FIFO_AW-1))-1],mem1[0:(1<<(FIFO_AW-1))-1];
 reg [FIFO_AW:0] wp,rp;
 reg ovf; assign o_overflow=ovf;
 wire [FIFO_AW:0] used=wp-rp;
 wire accept=i_en && used<=((1<<FIFO_AW)-3);
 wire [FIFO_AW-1:0] wa=wp[FIFO_AW-1:0],wb=wa+1'b1;
 wire we0=accept && (events==2 || (events==1 && !wp[0]));
 wire we1=accept && (events==2 || (events==1 && wp[0]));
 wire [FIFO_AW-2:0] addr0=wp[0]?wb[FIFO_AW-1:1]:wa[FIFO_AW-1:1];
 wire [FIFO_AW-2:0] addr1=wa[FIFO_AW-1:1];
 wire [18:0] data0=wp[0]?event1:event0,data1=wp[0]?event0:event1;
 wire [18:0] rsym=rp[0]?mem1[rp[FIFO_AW-1:1]]:mem0[rp[FIFO_AW-1:1]];
 // Up to two ordered events per cycle; unchanged controls consume no FIFO.
 always @* begin
  next_d=buf_d;next_k=buf_k;
  next_d[count*8 +:32]=i_rxd;next_k[count +:4]=i_rxk;
  available=count+4;cursor=0;events=0;event0=0;event1=0;
  next_vs=shadow_vs;next_hs=shadow_hs;next_bad=bad;ev=0;valid_ev=0;next_acquired=acquired;
  for(step=0;step<4;step=step+1) begin
   if(cursor<4 && available-cursor>=4 && events<2) begin
    ev=0;valid_ev=1;
    if(next_k[cursor +:4]==4'b1001 &&
       next_d[cursor*8 +:8]==8'hbc && next_d[(cursor+1)*8 +:8]==8'h28 &&
       next_d[(cursor+3)*8 +:8]==8'hbc &&
       (next_d[(cursor+2)*8 +:8]&8'h9f)==0) begin
     ev={1'b1,next_d[(cursor+2)*8+5],next_d[(cursor+2)*8+6],16'b0};cursor=cursor+4;next_acquired=1;
    end else if(!next_acquired) begin
     cursor=cursor+1;valid_ev=0;
    end else if(next_k[cursor +:3]==3'b101 &&
       next_d[cursor*8 +:8]==8'hbc && next_d[(cursor+1)*8 +:8]==8'h28 &&
       next_d[(cursor+2)*8 +:8]==8'hbc) begin
     // Inserted BC/28 pair before another K-started control.
     cursor=cursor+2;valid_ev=0;
    end else if(next_k[cursor +:2]==2'b10 &&
       next_d[(cursor+1)*8 +:8]==8'hbc && (next_d[cursor*8 +:8]&8'h9f)==0) begin
     // Only the status/end-K suffix remains after BC(K),28(D) removal.
     ev={1'b1,next_d[cursor*8+5],next_d[cursor*8+6],16'b0};cursor=cursor+2;
    end else if(next_k[cursor +:2]==0) begin
     ev={3'b000,next_d[cursor*8 +:16]};cursor=cursor+2;
    end else begin
     next_bad=1;next_acquired=0;cursor=cursor+1;valid_ev=0;
    end
    if(valid_ev && next_acquired && !ev[18]) begin
     if(events==0)event0=ev;else event1=ev;events=events+1;
    end
    if(valid_ev && next_acquired && ev[18]) begin
     if(ev[17]!=next_vs || ev[16]!=next_hs) begin
      if(events==0)event0=ev;else event1=ev;events=events+1;
      next_vs=ev[17];next_hs=ev[16];
     end
    end
   end
  end
  next_d=next_d>>(cursor*8);next_k=next_k>>cursor;next_count=available-cursor;
 end
 always @(posedge i_clk) begin
  if(we0)mem0[addr0]<=data0;
  if(we1)mem1[addr1]<=data1;
 end
 always @(posedge i_clk or negedge i_rst_n) begin
  if(!i_rst_n) begin
   buf_d<=0;buf_k<=0;count<=0;shadow_vs<=0;shadow_hs<=0;bad<=0;acquired<=0;wp<=0;rp<=0;
   o_vs<=0;o_hs<=0;o_de<=0;o_pix<=0;ovf<=0;
  end else if(!i_en) begin
   buf_d<=0;buf_k<=0;count<=0;shadow_vs<=0;shadow_hs<=0;bad<=0;acquired<=0;wp<=0;rp<=0;
   o_vs<=0;o_hs<=0;o_de<=0;ovf<=0;
  end else begin
   buf_d<=next_d;buf_k<=next_k;count<=next_count;bad<=next_bad;acquired<=next_acquired;
   ovf<=events>0 && !accept;
   if(accept) begin wp<=wp+events;shadow_vs<=next_vs;shadow_hs<=next_hs;end
   o_de<=0;
   if(wp!=rp) begin
    rp<=rp+1'b1;
    if(rsym[18])begin o_vs<=rsym[17];o_hs<=rsym[16];end
    else begin o_de<=1;o_pix<=rsym[15:0];end
   end
  end
 end
endmodule
