// RX-domain counters with a bundled-data request/ack snapshot to host clock.
module sfp_rx_diagnostics #(parameter NEW_PARSER=0)(
 input rx_clk,rx_rst_n,host_clk,host_rst_n,link_en,
 input [31:0] raw_d,input [3:0] raw_k,disp_err,decode_err,
 input [2:0] status,input [1:0] phase,input vs,de,malformed,overflow,
 output reg [511:0] host_snapshot);
 reg [31:0] c[0:15]; integer i;
 reg prev_vs,prev_link;reg [1:0] prev_phase;reg [31:0] frame_dec,frame_raw;
 reg [31:0] frame_disp,frame_decode;
 reg req,ack;reg [1:0] req_sync,ack_sync;reg [511:0] held;
 reg [511:0] data_sync0,data_sync1;
 reg [31:0] host_seq;
 reg [7:0] prev_byte;reg prev_k,prev_raw_valid;
 wire [2:0] matches50=
  ((prev_raw_valid && prev_k && prev_byte==8'hbc && !raw_k[0] && raw_d[7:0]==8'h50)?3'd1:3'd0)+
  ((raw_k[1:0]==1 && raw_d[7:0]==8'hbc && raw_d[15:8]==8'h50)?3'd1:3'd0)+
  ((raw_k[2:1]==1 && raw_d[15:8]==8'hbc && raw_d[23:16]==8'h50)?3'd1:3'd0)+
  ((raw_k[3:2]==1 && raw_d[23:16]==8'hbc && raw_d[31:24]==8'h50)?3'd1:3'd0);
 wire [2:0] matches28=
  ((prev_raw_valid && prev_k && prev_byte==8'hbc && !raw_k[0] && raw_d[7:0]==8'h28)?3'd1:3'd0)+
  ((raw_k[1:0]==1 && raw_d[7:0]==8'hbc && raw_d[15:8]==8'h28)?3'd1:3'd0)+
  ((raw_k[2:1]==1 && raw_d[15:8]==8'hbc && raw_d[23:16]==8'h28)?3'd1:3'd0)+
  ((raw_k[3:2]==1 && raw_d[23:16]==8'hbc && raw_d[31:24]==8'h28)?3'd1:3'd0);
 wire sof=vs && !prev_vs;
 always @(posedge rx_clk or negedge rx_rst_n) begin
  if(!rx_rst_n)begin
   for(i=0;i<16;i=i+1)c[i]<=0;
   prev_vs<=0;prev_link<=0;prev_phase<=0;frame_dec<=0;frame_raw<=0;frame_disp<=0;frame_decode<=0;
   req_sync<=0;ack<=0;held<=0;prev_byte<=0;prev_k<=0;prev_raw_valid<=0;
  end else begin
   req_sync<={req_sync[0],req};
   prev_vs<=vs;prev_link<=link_en;prev_phase<=phase;
   prev_byte<=raw_d[31:24];prev_k<=raw_k[3];prev_raw_valid<=link_en;
   c[0]<=32'h52580000 | (NEW_PARSER<<8) | (malformed<<1) | link_en;
   if(link_en)begin
    if(status==2)c[1]<=c[1]+1;
    if(status==1)c[2]<=c[2]+1;
    if(raw_k==2)c[3]<=c[3]+1;
    if(raw_k==4)c[4]<=c[4]+1;
    if(phase!=prev_phase)c[5]<=c[5]+1;
    if(|disp_err)frame_disp<=frame_disp+1;
    if(|decode_err)frame_decode<=frame_decode+1;
    c[10]<=c[10]+matches50;c[11]<=c[11]+matches28;
    frame_raw<=frame_raw+(raw_k==0?2:0);
    if(status>=4)c[12]<=c[12]+1;
   end
   if(de)begin frame_dec<=frame_dec+1;end
   if(overflow)c[13]<=c[13]+1;
   if(prev_link && !link_en)c[14]<=c[14]+1;
   if(sof)begin
    c[8]<=frame_dec;c[9]<=frame_raw;c[15]<=c[15]+1;c[6]<=frame_disp;c[7]<=frame_decode;
    frame_disp<=link_en && |disp_err?1:0;frame_decode<=link_en && |decode_err?1:0;
    frame_dec<=de?1:0;frame_raw<=link_en && raw_k==0?2:0;
   end
   if(req_sync[1]!=ack)begin
    for(i=0;i<16;i=i+1)held[i*32 +:32]<=c[i];
    ack<=req_sync[1];
   end
  end
 end
 // The source holds data until the next request. Two data stages and an
 // additional equality cycle precede consumption; host then requests again.
 always @(posedge host_clk or negedge host_rst_n) begin
  if(!host_rst_n)begin req<=1;ack_sync<=0;data_sync0<=0;data_sync1<=0;host_snapshot<=0;host_seq<=0;end
  else begin
   ack_sync<={ack_sync[0],ack};data_sync0<=held;data_sync1<=data_sync0;
   if(ack_sync[1]==req)begin host_snapshot<=data_sync1;host_seq<=host_seq+1;req<=~req;end
  end
 end
endmodule
