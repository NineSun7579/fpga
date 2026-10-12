// tb_cdc_valid.sv -- CDC valid-protocol probe with REAL ov5640_cdc + cam_fir3.
// Lane A: PCLK 84 MHz (11.905 ns), Lane B: PCLK 48 MHz (20.833 ns).
// Shared video_clk 131.25 MHz (7.619 ns). 640x480 pixels, 1 valid PCLK/pixel,
// 1896 PCLKs/row, 984 rows/frame. Checks video_valid cycles/frame and data order.
`timescale 1ns/1fs
module tb_cdc_valid;
GTP_GRS GRS_INST(.GRS_N(1'b1));
reg vclk = 0; always #(7.619/2.0) vclk = ~vclk;
reg pclkA = 0; always #(11.905/2.0) pclkA = ~pclkA;
reg pclkB = 0; always #(20.833/2.0) pclkB = ~pclkB;
reg rst = 1;

wire [15:0] vdA, vdB, fdA, fdB;
wire vvA, vvB, fvA, fvB, vhA, vhB, vsA, vsB;

reg [15:0] srcA_data = 0, srcB_data = 0;
reg srcA_valid = 0, srcB_valid = 0, srcA_hsync = 0, srcB_hsync = 0;
reg srcA_vsync = 0, srcB_vsync = 0;

ov5640_cdc #(.DATA_WIDTH(16), .DEVICE("PG")) cdcA(
  .cam_clk(pclkA), .cam_rst(rst),
  .s_data(srcA_data), .s_valid(srcA_valid), .s_hsync(srcA_hsync), .s_vsync(srcA_vsync),
  .video_clk(vclk), .video_rst(rst),
  .video_data(vdA), .video_valid(vvA), .video_hsync(vhA), .video_vsync(vsA));
cam_fir3 #(.DATA_WIDTH(16)) firA(
  .clk(vclk), .rst(rst), .in_valid(vvA), .in_pixel(vdA), .in_vsync(vsA),
  .out_valid(fvA), .out_pixel(fdA), .out_vsync());

ov5640_cdc #(.DATA_WIDTH(16), .DEVICE("PG")) cdcB(
  .cam_clk(pclkB), .cam_rst(rst),
  .s_data(srcB_data), .s_valid(srcB_valid), .s_hsync(srcB_hsync), .s_vsync(srcB_vsync),
  .video_clk(vclk), .video_rst(rst),
  .video_data(vdB), .video_valid(vvB), .video_hsync(vhB), .video_vsync(vsB));
cam_fir3 #(.DATA_WIDTH(16)) firB(
  .clk(vclk), .rst(rst), .in_valid(vvB), .in_pixel(vdB), .in_vsync(vsB),
  .out_valid(fvB), .out_pixel(fdB), .out_vsync());

// pixel sources: 1 PCLK valid per pixel, 640 px/row, 1896 PCLK/row, 480/984 rows
task automatic source_frame(input integer lane);
integer row, col, n, per;
begin
  for (row = 0; row < 984; row = row + 1) begin
    col = 0; n = 0;
    while (col < 1896) begin
      if (lane == 0) @(posedge pclkA); else @(posedge pclkB);
      if (lane == 0) begin srcA_valid = 0; end else begin srcB_valid = 0; end
      if (row < 480 && col < 1280 && (col % 2) == 1) begin
        per = row * 640 + col / 2;
        if (lane == 0) begin srcA_data = per[15:0]; srcA_valid = 1; srcA_hsync = 1; end
        else begin srcB_data = per[15:0]; srcB_valid = 1; srcB_hsync = 1; end
      end else begin
        if (lane == 0) begin srcA_hsync = (row < 480) && (col < 1280); end
        else begin srcB_hsync = (row < 480) && (col < 1280); end
      end
      if (lane == 0) srcA_vsync = (row < 3); else srcB_vsync = (row < 3);
      col = col + 1;
    end
  end
  if (lane == 0) begin srcA_valid = 0; srcA_hsync = 0; srcA_vsync = 0; end
  else begin srcB_valid = 0; srcB_hsync = 0; srcB_vsync = 0; end
end
endtask

// monitors in video_clk domain; frame delimited by video_vsync rising
integer cntA = 0, cntB = 0, chgA = 0, chgB = 0, dupA = 0, dupB = 0;
integer gapA = 0, gapB = 0, ordA = 0, ordB = 0;
integer lastA = -1, lastB = -1, framesA = 0, framesB = 0;
reg psA = 0, psB = 0;
always @(posedge vclk) begin
  if (rst) begin cntA = 0; chgA = 0; dupA = 0; gapA = 0; ordA = 0; lastA = -1; framesA = 0; psA = 0; end
  else begin
    if (vsA && !psA) begin
      $display("LANEA frame %0d valids=%0d changes=%0d dups=%0d gaps=%0d order_err=%0d",
               framesA, cntA, chgA, dupA, gapA, ordA);
      framesA = framesA + 1;
      cntA = 0; chgA = 0; dupA = 0; gapA = 0; ordA = 0; lastA = -1;
    end
    psA = vsA;
    if (vvA) begin
      cntA = cntA + 1;
      if (lastA == -1) begin lastA = vdA; chgA = chgA + 1; end
      else if (vdA == lastA) dupA = dupA + 1;
      else if (vdA == ((lastA + 1) & 16'hFFFF)) begin chgA = chgA + 1; lastA = vdA; end
      else if (vdA > lastA && vdA < lastA + 64) begin gapA = gapA + 1; lastA = vdA; end
      else begin ordA = ordA + 1; lastA = vdA; end
    end
  end
end
always @(posedge vclk) begin
  if (rst) begin cntB = 0; chgB = 0; dupB = 0; gapB = 0; ordB = 0; lastB = -1; framesB = 0; psB = 0; end
  else begin
    if (vsB && !psB) begin
      $display("LANEB frame %0d valids=%0d changes=%0d dups=%0d gaps=%0d order_err=%0d",
               framesB, cntB, chgB, dupB, gapB, ordB);
      framesB = framesB + 1;
      cntB = 0; chgB = 0; dupB = 0; gapB = 0; ordB = 0; lastB = -1;
    end
    psB = vsB;
    if (vvB) begin
      cntB = cntB + 1;
      if (lastB == -1) begin lastB = vdB; chgB = chgB + 1; end
      else if (vdB == lastB) dupB = dupB + 1;
      else if (vdB == ((lastB + 1) & 16'hFFFF)) begin chgB = chgB + 1; lastB = vdB; end
      else if (vdB > lastB && vdB < lastB + 64) begin gapB = gapB + 1; lastB = vdB; end
      else begin ordB = ordB + 1; lastB = vdB; end
    end
  end
end

initial begin
  repeat (10) @(posedge vclk);
  rst = 0;
  fork
    begin source_frame(0); source_frame(0); end
    begin source_frame(1); source_frame(1); end
  join
  repeat (2000) @(posedge vclk);
  $display("DONE cdc_valid_probe");
  $finish;
end
endmodule
