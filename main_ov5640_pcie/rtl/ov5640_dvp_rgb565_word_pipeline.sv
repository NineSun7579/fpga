`default_nettype none

/**
 * @file ov5640_dvp_rgb565_word_pipeline.sv
 * @brief Connect OV5640 DVP capture, RGB565 processing, and 128-bit packing.
 *
 * @details
 * This board-independent wrapper composes the existing capture/processing
 * stream with the RGB565 word packer. It defines no sensor configuration,
 * clock generation, CDC/FIFO, DDR3 transaction, PCIe TLP, or host protocol.
 * All stages use `cam_pclk`; a future integration layer must insert an
 * explicitly verified clock-domain bridge before DDR3 or PCIe user clocks.
 *
 * @par Interface contract
 * - Camera bytes are sampled according to the capture module contract.
 * - Processed RGB565 pixels are accumulated in receive order.
 * - Output words use the packer contract: pixel 0 occupies the low 16 bits,
 *   and `word_keep` marks valid byte lanes.
 * - Frame/line events and protocol errors are propagated by the packer.
 *
 * @par Assumptions
 * - The polarity and byte ordering parameters match the approved OV5640
 *   configuration when this wrapper is integrated on hardware.
 */
module ov5640_dvp_rgb565_word_pipeline #(
    parameter logic VSYNC_ACTIVE_LEVEL = 1'b1,
    parameter logic HREF_ACTIVE_LEVEL  = 1'b1,
    parameter logic FIRST_BYTE_IS_HIGH = 1'b1
) (
    input  wire logic         rst_n,
    input  wire logic         cam_pclk,
    input  wire logic         cam_vsync,
    input  wire logic         cam_href,
    input  wire logic [7:0]   cam_data,
    output logic              word_valid,
    output logic [127:0]      word_data,
    output logic [15:0]       word_keep,
    output logic              word_frame_start,
    output logic              word_line_start,
    output logic              word_line_end,
    output logic              word_frame_end,
    output logic              word_protocol_error
);

    logic        pixel_valid;
    logic [15:0] pixel_data;
    logic        frame_start;
    logic        line_start;
    logic        line_end;
    logic        frame_end;
    logic [15:0] pixel_x;
    logic [15:0] pixel_y;
    logic        protocol_error;

    ov5640_dvp_rgb565_pipeline #(
        .VSYNC_ACTIVE_LEVEL (VSYNC_ACTIVE_LEVEL),
        .HREF_ACTIVE_LEVEL  (HREF_ACTIVE_LEVEL),
        .FIRST_BYTE_IS_HIGH (FIRST_BYTE_IS_HIGH)
    ) u_capture_process (
        .rst_n          (rst_n),
        .cam_pclk       (cam_pclk),
        .cam_vsync      (cam_vsync),
        .cam_href       (cam_href),
        .cam_data       (cam_data),
        .pixel_valid    (pixel_valid),
        .pixel_data     (pixel_data),
        .frame_start    (frame_start),
        .line_start     (line_start),
        .line_end       (line_end),
        .frame_end      (frame_end),
        .pixel_x        (pixel_x),
        .pixel_y        (pixel_y),
        .protocol_error (protocol_error)
    );

    rgb565_word_packer u_word_packer (
        .rst_n              (rst_n),
        .clk                (cam_pclk),
        .in_valid           (pixel_valid),
        .in_data            (pixel_data),
        .in_frame_start     (frame_start),
        .in_line_start      (line_start),
        .in_line_end        (line_end),
        .in_frame_end       (frame_end),
        .in_protocol_error  (protocol_error),
        .word_valid         (word_valid),
        .word_data          (word_data),
        .word_keep          (word_keep),
        .word_frame_start   (word_frame_start),
        .word_line_start    (word_line_start),
        .word_line_end      (word_line_end),
        .word_frame_end     (word_frame_end),
        .word_protocol_error(word_protocol_error)
    );

endmodule

`default_nettype wire
