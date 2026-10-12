`timescale 1ns/1ps
// Actual frozen ROM, natural initialization and synthetic transaction completion.
// The SCCB electrical master and sensor are outside this test's scope.
module tb_config;
reg clk=0, rst_n=0;
always #5 clk=~clk;
wire [5:0] exec, done_init, rw;
wire [23:0] data [0:5];
reg [5:0] done=0;
integer count [0:5];
reg [23:0] baseline [0:263];
integer j, index;
ov5640_i2c_rgb565_cfg default_rom (
 .clk(clk),.rst_n(rst_n),.i2c_data_r(8'h56),.i2c_done(done[0]),
 .cmos_h_pixel(13'd640),.cmos_v_pixel(13'd480),
 .total_h_pixel(13'd1896),.total_v_pixel(13'd984),
 .i2c_exec(exec[0]),.i2c_data(data[0]),.i2c_rh_wl(rw[0]),.init_done(done_init[0]));
ov5640_i2c_rgb565_cfg #(.SENSOR_PLL_MULT(8'h54)) cam2 (
 .clk(clk),.rst_n(rst_n),.i2c_data_r(8'h56),.i2c_done(done[1]),
 .cmos_h_pixel(13'd640),.cmos_v_pixel(13'd480),
 .total_h_pixel(13'd1896),.total_v_pixel(13'd984),
 .i2c_exec(exec[1]),.i2c_data(data[1]),.i2c_rh_wl(rw[1]),.init_done(done_init[1]));
genvar c;
generate for(c=2;c<6;c=c+1) begin: candidate_cam
ov5640_i2c_rgb565_cfg #(.SENSOR_PLL_MULT(8'h38)) rom (
 .clk(clk),.rst_n(rst_n),.i2c_data_r(8'h56),.i2c_done(done[c]),
 .cmos_h_pixel(c==4 ? 13'd320 : c==5 ? 13'd1280 : 13'd640),
 .cmos_v_pixel(c==4 ? 13'd240 : c==5 ? 13'd720 : 13'd480),
 .total_h_pixel(13'd1896),.total_v_pixel(13'd984),
 .i2c_exec(exec[c]),.i2c_data(data[c]),.i2c_rh_wl(rw[c]),.init_done(done_init[c]));
end endgenerate
always @(posedge clk) done <= exec;
task fail;
input [255:0] reason;
begin $display("FAIL %s", reason); $fatal(1); end
endtask
always @(negedge clk) if(rst_n) begin
 for(j=0;j<6;j=j+1) if(exec[j]) begin
  index=count[j];
  if(index>=264) fail("extra register transaction");
  $display("EMIT profile=%0d index=%0d rw=%0d reg=%04h value=%02h",j,index,rw[j],data[j][23:8],data[j][7:0]);
  if(rw[j] !== (index<2)) fail("read/write sequence");
  if(j==0) baseline[index]=data[j];
  if(j!=0) begin
   if(index==209) begin
    if(j==1 && data[j]!==24'h303654) fail("CAM2 PLL 84 MHz multiplier");
     if(j>=2 && data[j]!==24'h303638) fail("CAM34 PLL 56 MHz multiplier");
   end else if(!(j>=4 && index>=223 && index<=226) && data[j]!==baseline[index]) fail("unintended ROM difference");
  end
  case(index)
   209: if(j==0 && data[j]!==24'h303654) fail("default PLL");
   223: if(data[j]!==(j==4 ? 24'h380801 : j==5 ? 24'h380805 : 24'h380802)) fail("640 width high");
   224: if(data[j]!==(j==4 ? 24'h380940 : j==5 ? 24'h380900 : 24'h380980)) fail("640 width low");
   225: if(data[j]!==(j==4 ? 24'h380a00 : j==5 ? 24'h380a02 : 24'h380a01)) fail("480 height high");
   226: if(data[j]!==(j==4 ? 24'h380bf0 : j==5 ? 24'h380bd0 : 24'h380be0)) fail("480 height low");
   227: if(data[j]!==24'h380c07) fail("HTS high");
   228: if(data[j]!==24'h380d68) fail("HTS low");
   229: if(data[j]!==24'h380e03) fail("VTS high");
   230: if( data[j]!==24'h380fd8) fail("baseline VTS low");
   236: if(data[j]!==24'h3a0217) fail("60Hz exposure high");
   237: if(data[j]!==24'h3a0310) fail("60Hz exposure low");
   238: if(data[j]!==24'h3a1417) fail("first 50Hz exposure high");
   239: if(data[j]!==24'h3a1510) fail("first 50Hz exposure low");
   246: if(data[j]!==24'h3a1402) fail("final 50Hz exposure high");
   247: if(data[j]!==24'h3a15e0) fail("final 50Hz exposure low");
   263: if(data[j]!==24'h301900) fail("ROM last 9-bit index");
  endcase
  count[j]=count[j]+1;
 end
 if(&done_init) begin
  for(j=0;j<6;j=j+1) if(count[j]!=264) fail("incomplete ROM");
  $display("PASS CONFIG_ROM 6 profiles 264 transactions each; additional 320x240/1280x720 encoding cases; VTS 984=03d8 all cameras; 640x480; CAM12 PLL54 CAM34 PLL38");
  $finish;
 end
end
initial begin
 for(j=0;j<6;j=j+1) count[j]=0;
 #21 rst_n=1;
 #1000000 fail("initialization timeout");
end
endmodule
