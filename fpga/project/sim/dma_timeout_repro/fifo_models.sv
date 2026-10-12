// Behavioral contracts of the configured IP: 32->128 registered read,
// then 128-bit FWFT. Reduced DRM capacity intentionally exercises overflow.
module ov5640_ddr_fifo_DRM #(parameter DEPTH=32)(
 input clk,rst,wr_en,rd_en,input [31:0] wr_data,
 output wr_full,rd_empty,almost_full,almost_empty,output reg [127:0] rd_data);
 reg [31:0] mem[0:DEPTH-1];
 integer wp=0,rp=0,count=0,j;
 wire push=wr_en&&!wr_full, pop=rd_en&&!rd_empty;
 assign wr_full=count==DEPTH;
 assign rd_empty=count<4;
 assign almost_full=count>=DEPTH-4;
 assign almost_empty=count<8;
 always @(posedge clk) begin
  if(rst)begin wp<=0;rp<=0;count<=0;rd_data<=0;end
  else begin
   if(push)begin mem[wp]<=wr_data;wp<=(wp+1)%DEPTH;end
   if(pop)begin
    for(j=0;j<4;j=j+1)rd_data[j*32+:32]<=mem[(rp+j)%DEPTH];
    rp<=(rp+4)%DEPTH;
   end
   case({push,pop})2'b10:count<=count+1;2'b01:count<=count-4;2'b11:count<=count-3;endcase
  end
 end
endmodule
module ov5640_ddr_fifo(input clk,rst,wr_en,rd_en,input [127:0] wr_data,
 output full,empty,almost_full,almost_empty,output [127:0] rd_data);
 reg [127:0] mem[0:15];integer wp=0,rp=0,count=0;
 wire push=wr_en&&!full,pop=rd_en&&!empty;
 assign full=count==16;assign empty=count==0;
 assign almost_full=count>=15;assign almost_empty=count<4;
 assign rd_data=mem[rp];
 always @(posedge clk)begin
  if(rst)begin wp<=0;rp<=0;count<=0;end
  else begin
   if(push)begin mem[wp]<=wr_data;wp<=(wp+1)%16;end
   if(pop)rp<=(rp+1)%16;
   case({push,pop})2'b10:count<=count+1;2'b01:count<=count-1;endcase
  end
 end
endmodule
