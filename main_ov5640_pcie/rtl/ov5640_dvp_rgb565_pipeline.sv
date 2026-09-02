`default_nettype none

/**
 * @file ov5640_dvp_rgb565_pipeline.sv
 * @brief Connect OV5640 DVP capture to the first image-processing stage.
 *
 * @details
 * This board-independent wrapper combines byte capture and RGB565 grayscale
 * conversion. It is a stream-only product slice: sensor programming, clock
 * generation, CDC/FIFO, frame storage, DDR3, and PCIe remain outside the
 * wrapper.
 *
 * @par Interface contract
 * - The camera input is sampled in the `cam_pclk` domain.
 * - The grayscale output is visible one additional `cam_pclk` after capture.
 * - Frame/line events and coordinates are preserved through both stages.
 * - `protocol_error` reports capture-stage protocol errors with the same
 *   processing latency.
 *
 * @par Assumptions
 * - `VSYNC_ACTIVE_LEVEL`, `HREF_ACTIVE_LEVEL`, and `FIRST_BYTE_IS_HIGH` match
 *   the approved OV5640 configuration when this wrapper is integrated.
 */
module ov5640_dvp_rgb565_pipeline #(
    parameter logic VSYNC_ACTIVE_LEVEL = 1'b1,
    parameter logic HREF_ACTIVE_LEVEL  = 1'b1,
    parameter logic FIRST_BYTE_IS_HIGH = 1'b1
) (
    input  wire logic        rst_n,
    input  wire logic        cam_pclk,
    input  wire logic        cam_vsync,
    input  wire logic        cam_href,
    input  wire logic [7:0]  cam_data,
    output logic             pixel_valid,
    output logic [15:0]      pixel_data,
    output logic             frame_start,
    output logic             line_start,
    output logic             line_end,
    output logic             frame_end,
    output logic [15:0]      pixel_x,
    output logic [15:0]      pixel_y,
    output logic             protocol_error
);

    logic        captured_valid;
    logic [15:0] captured_data;
    logic        captured_frame_start;
    logic        captured_line_start;
    logic        captured_line_end;
    logic        captured_frame_end;
    logic [15:0] captured_x;
    logic [15:0] captured_y;
    logic        captured_protocol_error;

    ov5640_dvp_rgb565_capture #(
        .VSYNC_ACTIVE_LEVEL (VSYNC_ACTIVE_LEVEL),
        .HREF_ACTIVE_LEVEL  (HREF_ACTIVE_LEVEL),
        .FIRST_BYTE_IS_HIGH (FIRST_BYTE_IS_HIGH)
    ) u_capture (
        .rst_n          (rst_n),
        .cam_pclk       (cam_pclk),
        .cam_vsync      (cam_vsync),
        .cam_href       (cam_href),
        .cam_data       (cam_data),
        .pixel_valid    (captured_valid),
        .pixel_data     (captured_data),
        .frame_start    (captured_frame_start),
        .line_start     (captured_line_start),
        .line_end       (captured_line_end),
        .frame_end      (captured_frame_end),
        .pixel_x        (captured_x),
        .pixel_y        (captured_y),
        .protocol_error (captured_protocol_error)
    );

    rgb565_grayscale u_grayscale (
        .rst_n              (rst_n),
        .cam_pclk           (cam_pclk),
        .pixel_valid        (captured_valid),
        .pixel_data         (captured_data),
        .frame_start        (captured_frame_start),
        .line_start         (captured_line_start),
        .line_end           (captured_line_end),
        .frame_end          (captured_frame_end),
        .pixel_x            (captured_x),
        .pixel_y            (captured_y),
        .protocol_error     (captured_protocol_error),
        .out_valid          (pixel_valid),
        .out_data           (pixel_data),
        .out_frame_start    (frame_start),
        .out_line_start     (line_start),
        .out_line_end       (line_end),
        .out_frame_end      (frame_end),
        .out_x              (pixel_x),
        .out_y              (pixel_y),
        .out_protocol_error (protocol_error)
    );

endmodule

`default_nettype wire
