`default_nettype none

/**
 * @file ov5640_dvp_rgb565_dma_staging_pipeline.sv
 * @brief Connect OV5640 DVP processing to the board-independent DMA staging path.
 *
 * @details
 * This wrapper composes M1-A/M2-A/M3-A, the M3-B AXIS staging adapter, and the
 * frame accounting descriptor. It does not instantiate DDR3/PCIe IP, cross a
 * clock domain, or assign a host address. `staging_user` uses the M3-B project
 * staging encoding and is not a vendor PCIe `tuser` contract.
 *
 * @par Interface contract
 * - Camera input follows the existing DVP capture contract.
 * - `staging_ready` and the accounting input readiness jointly apply
 *   backpressure before a beat is accepted from the camera-side word packer.
 * - A frame descriptor is emitted after the staging stream accepts frame end.
 */
module ov5640_dvp_rgb565_dma_staging_pipeline #(
    parameter logic VSYNC_ACTIVE_LEVEL = 1'b1,
    parameter logic HREF_ACTIVE_LEVEL  = 1'b1,
    parameter logic FIRST_BYTE_IS_HIGH = 1'b1
) (
    input  wire logic         rst_n,
    input  wire logic         cam_pclk,
    input  wire logic         cam_vsync,
    input  wire logic         cam_href,
    input  wire logic [7:0]   cam_data,
    output logic              staging_valid,
    input  wire logic         staging_ready,
    output logic [127:0]      staging_data,
    output logic [3:0]        staging_keep,
    output logic              staging_last,
    output logic [7:0]        staging_user,
    output logic              desc_valid,
    input  wire logic         desc_ready,
    output logic [31:0]       desc_bytes,
    output logic [31:0]       desc_beats,
    output logic              desc_protocol_error
);
    logic [127:0] word_data;
    logic [15:0]  word_keep;
    logic         word_valid;
    logic         word_frame_start;
    logic         word_line_start;
    logic         word_line_end;
    logic         word_frame_end;
    logic         word_protocol_error;
    logic         adapter_ready;
    logic         accounting_ready;
    logic         frame_end_pending;
    logic [4:0]   accounting_user;

    ov5640_dvp_rgb565_word_pipeline #(
        .VSYNC_ACTIVE_LEVEL (VSYNC_ACTIVE_LEVEL),
        .HREF_ACTIVE_LEVEL  (HREF_ACTIVE_LEVEL),
        .FIRST_BYTE_IS_HIGH(FIRST_BYTE_IS_HIGH)
    ) u_word_pipeline (
        .rst_n              (rst_n), .cam_pclk(cam_pclk), .cam_vsync(cam_vsync),
        .cam_href           (cam_href), .cam_data(cam_data),
        .word_valid         (word_valid), .word_data(word_data), .word_keep(word_keep),
        .word_frame_start   (word_frame_start), .word_line_start(word_line_start),
        .word_line_end      (word_line_end), .word_frame_end(word_frame_end),
        .word_protocol_error(word_protocol_error)
    );

    rgb565_word_to_axis4_adapter u_axis4_adapter (
        .rst_n(rst_n), .clk(cam_pclk), .in_valid(word_valid), .in_ready(adapter_ready),
        .in_data(word_data), .in_keep(word_keep), .in_frame_start(word_frame_start),
        .in_line_start(word_line_start), .in_line_end(word_line_end),
        .in_frame_end(1'b0), .in_protocol_error(word_protocol_error),
        .out_valid(staging_valid), .out_ready(staging_ready && accounting_ready),
        .out_data(staging_data), .out_keep(staging_keep), .out_last(staging_last),
        .out_user(staging_user)
    );

    always_comb begin
        accounting_user = staging_user[4:0];
        if (frame_end_pending && staging_last) begin
            accounting_user[3] = 1'b1;
        end
    end

    always_ff @(posedge cam_pclk or negedge rst_n) begin
        if (!rst_n) begin
            frame_end_pending <= 1'b0;
        end else begin
            if (word_valid && word_frame_end) begin
                frame_end_pending <= 1'b1;
            end
            if (staging_valid && staging_ready && accounting_ready && staging_last) begin
                frame_end_pending <= 1'b0;
            end
        end
    end

    rgb565_axis4_frame_accounting u_frame_accounting (
        .rst_n(rst_n), .clk(cam_pclk), .in_valid(staging_valid),
        .in_ready(accounting_ready), .in_keep(staging_keep),
        .in_user(accounting_user),
        .desc_valid(desc_valid), .desc_ready(desc_ready), .desc_bytes(desc_bytes),
        .desc_beats(desc_beats), .desc_protocol_error(desc_protocol_error)
    );

    // The camera-side packer has no backpressure; this status remains internal
    // until a CDC/FIFO contract is approved for the final integration.
    logic unused_adapter_ready;
    assign unused_adapter_ready = adapter_ready;
endmodule

`default_nettype wire
