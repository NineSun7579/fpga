// Candidate only. Dual-clock register-array FIFO, 3-bit ordered tokens.
// Reset both domains together. Physical CDC constraints are integration work.
module cdc_order_meta #(parameter A=11)(
 input wc,wr,put,input [2:0] din,output full,
 input rc,rr,pop,output [2:0] head,output empty);
 reg [2:0] mem[0:(1<<A)-1];
 reg [A:0] wb,wg,rb,rg;
 (* async_reg="true" *) reg [A:0] rs1,rs2,ws1,ws2;
 wire [A:0] wn=wb+1'b1;
 // Conservative: reserve one slot. A must be >=2.
 assign full=((wn^(wn>>1))=={~rs2[A:A-1],rs2[A-2:0]});
 assign empty=(rg==ws2);
 assign head=mem[rb[A-1:0]];
 always @(posedge wc or posedge wr) begin
  if(wr) begin wb<=0;wg<=0;rs1<=0;rs2<=0;end
  else begin
   rs1<=rg;rs2<=rs1;
   if(put&&!full) begin mem[wb[A-1:0]]<=din;wb<=wn;wg<=wn^(wn>>1);end
  end
 end
 wire [A:0] rn=rb+1'b1;
 always @(posedge rc or posedge rr) begin
  if(rr) begin rb<=0;rg<=0;ws1<=0;ws2<=0;end
  else begin
   ws1<=wg;ws2<=ws1;
   if(pop&&!empty) begin rb<=rn;rg<=rn^(rn>>1);end
  end
 end
endmodule
