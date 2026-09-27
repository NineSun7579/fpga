// tb_cdc_pattern.sv -- which PCLK-side pattern reproduces ~1290240 axi valids?
// Modes: 0=ideal 640px/row every-other-PCLK; 1=back-to-back valids during active;
// 2=valid every-other-PCLK across FULL row (blanking included).
`timescale 1ns/1fs
module tb_cdc_pattern;
GTP_GRS GRS_INST(.GRS_N(1'b1));
reg vclk = 0; always #(7.619/2.0) vclk = ~vclk;
reg pclk = 0; always #(11.905/2.0) pclk = ~pclk;
reg rst = 1;
wire [15:0] vd; wire vv, vh, vs;
reg [15:0] s_data = 0; reg s_valid = 0, s_hsync = 0, s_vsync = 0;
ov5640_cdc #(.DATA_WIDTH(16), .DEVICE("PG")) dut(
  .cam_clk(pclk), .cam_rst(rst),
  .s_data(s_data), .s_valid(s_valid), .s_hsync(s_hsync), .s_vsync(s_vsync),
  .video_clk(vclk), .video_rst(rst),
  .video_data(vd), .video_valid(vv), .video_hsync(vh), .video_vsync(vs));

integer mode;
integer cnt = 0, frames = 0, offered = 0;
reg ps = 0;
always @(posedge vclk) begin
  if (rst) begin cnt = 0; frames = 0; ps = 0; end
  else begin
    if (vs && !ps) begin
      $display("MODE %0d frame %0d axi_valids=%0d offered=%0d", mode, frames, cnt, offered);
      frames = frames + 1; cnt = 0; offered = 0;
    end
    ps = vs;
    if (vv) cnt = cnt + 1;
  end
end

task automatic run_mode(input integer m);
integer row, col, n;
begin
  mode = m; n = 0;
  for (row = 0; row < 984; row = row + 1) begin
    col = 0;
    while (col < 1896) begin
      @(posedge pclk);
      s_valid = 0;
      if (m == 0) begin
        if (row < 480 && col < 1280 && (col % 2) == 1) begin s_data = n[15:0]; s_valid = 1; n = n + 1; offered = offered + 1; end
      end else if (m == 1) begin
        if (row < 480 && col < 1280) begin s_data = n[15:0]; s_valid = 1; n = n + 1; offered = offered + 1; end
      end else begin
        if (row < 480) begin s_data = n[15:0]; s_valid = (col % 2); if (col % 2) begin n = n + 1; offered = offered + 1; end end
      end
      s_hsync = (row < 480) && (col < 1280);
      s_vsync = (row < 3);
      col = col + 1;
    end
  end
  s_valid = 0; s_hsync = 0; s_vsync = 0;
  repeat (500) @(posedge vclk);
end
endtask

initial begin
  repeat (10) @(posedge vclk);
  rst = 0;
  run_mode(0);
  run_mode(1);
  run_mode(2);
  $display("DONE pattern_probe");
  $finish;
end
endmodule
