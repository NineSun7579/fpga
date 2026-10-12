// Simulation-only FIFO boundary models. DUT wrapper/gate/packer/controller
// compile directly from frozen V7. No vendor primitive timing is claimed.
module ov5640_ddr_fifo_DRM(input clk,rst,wr_en,input [31:0] wr_data,
 output wr_full,input rd_en,output reg [127:0] rd_data,
 output rd_empty,almost_full,almost_empty);
 reg [31:0] mem[0:4095];
 integer wp=0,rp=0,count=0;
 assign wr_full=count>=4096;
 assign almost_full=count>=4080;
 assign rd_empty=count<4;
 assign almost_empty=count<8;
 always @(posedge clk) begin
  if(rst) begin wp<=0;rp<=0;count<=0;rd_data<=0;end
  else begin
   if(wr_en&&!wr_full) begin mem[wp]<=wr_data;wp<=(wp+1)%4096;end
   if(rd_en&&!rd_empty) begin
    rd_data<={mem[(rp+3)%4096],mem[(rp+2)%4096],mem[(rp+1)%4096],mem[rp]};
    rp<=(rp+4)%4096;
   end
   count<=count+((wr_en&&!wr_full)?1:0)-((rd_en&&!rd_empty)?4:0);
  end
 end
endmodule
module ov5640_ddr_fifo(input clk,rst,wr_en,input [127:0] wr_data,
 output full,input rd_en,output [127:0] rd_data,
 output empty,almost_full,almost_empty);
 reg [127:0] mem[0:15];
 integer wp=0,rp=0,count=0;
 assign full=count>=16;
 assign almost_full=count>=15;
 assign empty=count==0;
 assign almost_empty=count<=1;
 assign rd_data=mem[rp];
 always @(posedge clk) begin
  if(rst) begin wp<=0;rp<=0;count<=0;end
  else begin
   if(wr_en&&!full) begin mem[wp]<=wr_data;wp<=(wp+1)%16;end
   if(rd_en&&!empty) rp<=(rp+1)%16;
   count<=count+((wr_en&&!full)?1:0)-((rd_en&&!empty)?1:0);
  end
 end
endmodule
