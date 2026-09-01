`timescale 1ns/1ns

module tb_dual_ov5640_dri;

localparam integer EXPECTED_PIXELS_PER_FRAME = 32 * 4 / 2;
integer pixel_count_1;
integer pixel_count_2;
integer frame_count_1;
integer frame_count_2;

reg clk_50m;
reg rst_n;
reg [12:0] cmos_h_pixel;
reg [12:0] cmos_v_pixel;
reg [12:0] total_h_pixel;
reg [12:0] total_v_pixel;
reg capture_start;
reg cmos_clk;

wire cam_init_done_1;
wire cam_init_done_2;
wire cmos_frame_vsync_1;
wire cmos_frame_vsync_2;
wire cmos_frame_valid_1;
wire cmos_frame_valid_2;
wire [15:0] cmos_frame_data_1;
wire [15:0] cmos_frame_data_2;
wire cmos_pclk_1;
wire cmos_pclk_2;
wire cmos_vsync_1;
wire cmos_vsync_2;
wire cmos_href_1;
wire cmos_href_2;
wire [7:0] cmos_data_1;
wire [7:0] cmos_data_2;
wire cam_sda_1;
wire cam_sda_2;

initial begin
  rst_n = 1'b0;
  capture_start = 1'b1;
  cmos_h_pixel = 13'd1920;
  cmos_v_pixel = 13'd1080;
  total_h_pixel = 13'd2200;
  total_v_pixel = 13'd1125;
  pixel_count_1 = 0;
  pixel_count_2 = 0;
  frame_count_1 = 0;
  frame_count_2 = 0;
  #200 rst_n = 1'b1;
end

initial clk_50m = 1'b0;
always #10 clk_50m = ~clk_50m;

initial cmos_clk = 1'b0;
always #11 cmos_clk = ~cmos_clk;

ov5640_dri u_ov5640_dri_1 (
  .clk(clk_50m),
  .rst_n(rst_n),
  .cam_pclk(cmos_pclk_1),
  .cam_vsync(cmos_vsync_1),
  .cam_href(cmos_href_1),
  .cam_data(cmos_data_1),
  .cam_rst_n(),
  .cam_pwdn(),
  .cam_scl(),
  .cam_sda(cam_sda_1),
  .cmos_h_pixel(cmos_h_pixel),
  .cmos_v_pixel(cmos_v_pixel),
  .total_h_pixel(total_h_pixel),
  .total_v_pixel(total_v_pixel),
  .capture_start(capture_start),
  .cam_init_done(cam_init_done_1),
  .cmos_frame_vsync(cmos_frame_vsync_1),
  .cmos_frame_href(),
  .cmos_frame_valid(cmos_frame_valid_1),
  .cmos_frame_data(cmos_frame_data_1)
);

ov5640_dri u_ov5640_dri_2 (
  .clk(clk_50m),
  .rst_n(rst_n),
  .cam_pclk(cmos_pclk_2),
  .cam_vsync(cmos_vsync_2),
  .cam_href(cmos_href_2),
  .cam_data(cmos_data_2),
  .cam_rst_n(),
  .cam_pwdn(),
  .cam_scl(),
  .cam_sda(cam_sda_2),
  .cmos_h_pixel(cmos_h_pixel),
  .cmos_v_pixel(cmos_v_pixel),
  .total_h_pixel(total_h_pixel),
  .total_v_pixel(total_v_pixel),
  .capture_start(capture_start),
  .cam_init_done(cam_init_done_2),
  .cmos_frame_vsync(cmos_frame_vsync_2),
  .cmos_frame_href(),
  .cmos_frame_valid(cmos_frame_valid_2),
  .cmos_frame_data(cmos_frame_data_2)
);

Video_Image_Simulate_CMOS #(
  .CMOS_VSYNC_VALID(1'b1),
  .IMG_HDISP(11'd32),
  .IMG_VDISP(11'd4)
) u_cmos_model_1 (
  .rst_n(rst_n & cam_init_done_1),
  .cmos_xclk(cmos_clk),
  .cmos_pclk(cmos_pclk_1),
  .cmos_vsync(cmos_vsync_1),
  .cmos_href(cmos_href_1),
  .cmos_data(cmos_data_1)
);

Video_Image_Simulate_CMOS #(
  .CMOS_VSYNC_VALID(1'b1),
  .IMG_HDISP(11'd32),
  .IMG_VDISP(11'd4)
) u_cmos_model_2 (
  .rst_n(rst_n & cam_init_done_2),
  .cmos_xclk(cmos_clk),
  .cmos_pclk(cmos_pclk_2),
  .cmos_vsync(cmos_vsync_2),
  .cmos_href(cmos_href_2),
  .cmos_data(cmos_data_2)
);

initial begin
  #1000;
  force u_ov5640_dri_1.cam_init_done = 1'b1;
  force u_ov5640_dri_2.cam_init_done = 1'b1;
end

always @(posedge cmos_pclk_1 or negedge rst_n)
  if (!rst_n)
    pixel_count_1 = 0;
  else if (cmos_frame_valid_1)
    pixel_count_1 = pixel_count_1 + 1;

always @(posedge cmos_pclk_2 or negedge rst_n)
  if (!rst_n)
    pixel_count_2 = 0;
  else if (cmos_frame_valid_2)
    pixel_count_2 = pixel_count_2 + 1;

always @(negedge cmos_frame_vsync_1)
  if (rst_n && cam_init_done_1) begin
    frame_count_1 = frame_count_1 + 1;
    if (pixel_count_1 != EXPECTED_PIXELS_PER_FRAME)
      $fatal(1, "camera 1 frame %0d has %0d RGB565 words", frame_count_1, pixel_count_1);
    pixel_count_1 = 0;
  end

always @(negedge cmos_frame_vsync_2)
  if (rst_n && cam_init_done_2) begin
    frame_count_2 = frame_count_2 + 1;
    if (pixel_count_2 != EXPECTED_PIXELS_PER_FRAME)
      $fatal(1, "camera 2 frame %0d has %0d RGB565 words", frame_count_2, pixel_count_2);
    pixel_count_2 = 0;
    if (frame_count_1 == 3 && frame_count_2 == 3) begin
      $display("PASS: dual OV5640 RGB565 capture loop complete");
      $finish;
    end
  end

initial begin
  #200_000;
  $fatal(1, "dual OV5640 simulation timeout");
end

endmodule
