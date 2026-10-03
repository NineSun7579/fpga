// Startup-only sink. Pixel CDC is downstream of the real SCCB/control path.
module ov5640_cdc #(parameter DATA_WIDTH=24, parameter DEVICE="PG")(
  output [31:0] dbg_cdc_input, dbg_cdc_output, dbg_cdc_drop, dbg_cdc_seq,
  input cam_clk, cam_rst, input [DATA_WIDTH-1:0] s_data,
  input s_valid, s_hsync, s_vsync, video_clk, video_rst,
  output [DATA_WIDTH-1:0] video_data,
  output video_valid, video_hsync, video_vsync);
  assign dbg_cdc_input=0, dbg_cdc_output=0, dbg_cdc_drop=0, dbg_cdc_seq=0;
  assign video_data=0, video_valid=0, video_hsync=0, video_vsync=0;
endmodule
