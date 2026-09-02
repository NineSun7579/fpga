`default_nettype none

/**
 * @file ov5640_dvp_rgb565_capture.sv
 * @brief Capture an 8-bit source-synchronous DVP stream as RGB565 pixels.
 *
 * @details
 * This module owns only byte pairing and frame/line event generation in the
 * `cam_pclk` clock domain. It does not configure the sensor, generate MCLK,
 * cross clock domains, buffer frames, process pixels, or drive PCIe.
 *
 * @par Interface contract
 * - `cam_data` is sampled on the rising edge of `cam_pclk` while `cam_href`
 *   equals `HREF_ACTIVE_LEVEL`.
 * - Two accepted bytes form one pixel. By default the first byte is the
 *   RGB565 high byte; `FIRST_BYTE_IS_HIGH` selects the alternate ordering.
 * - A transition of `cam_vsync` into `VSYNC_ACTIVE_LEVEL` closes the previous
 *   observed frame and arms the next frame. The first pixel after that marker
 *   asserts `frame_start`.
 * - `line_start` is aligned with the first pixel in an HREF window. `line_end`
 *   is a one-cycle event after an HREF window closes and a complete line was
 *   observed.
 * - `pixel_x` and `pixel_y` identify the pixel presented with `pixel_valid`.
 *   Coordinates are zero-based and increment within the 16-bit range.
 *
 * @par Clock and reset
 * - Clock: `cam_pclk`, rising edge.
 * - Reset: `rst_n`, asynchronous assertion and release behavior must be
 *   constrained by the integrating design.
 *
 * @par Assumptions
 * - `cam_vsync` and `cam_href` meet the source-synchronous timing contract at
 *   the `cam_pclk` input of this module.
 * - A frame marker precedes the first line that is intended for capture.
 *
 * @warning
 * The polarity and exact phase of OV5640 timing signals are board and sensor
 * configuration facts. Keep these parameters aligned with the approved sensor
 * register configuration and verify them at integration time.
 */
module ov5640_dvp_rgb565_capture #(
    parameter logic VSYNC_ACTIVE_LEVEL = 1'b1,
    parameter logic HREF_ACTIVE_LEVEL  = 1'b1,
    parameter logic FIRST_BYTE_IS_HIGH = 1'b1
) (
    input  wire logic        rst_n,
    input  wire logic        cam_pclk,
    input  wire logic        cam_vsync,
    input  wire logic        cam_href,
    input  wire logic [7:0]  cam_data,
    output logic        pixel_valid,
    output logic [15:0] pixel_data,
    output logic        frame_start,
    output logic        line_start,
    output logic        line_end,
    output logic        frame_end,
    output logic [15:0] pixel_x,
    output logic [15:0] pixel_y,
    output logic        protocol_error
);

    logic        vsync_active_d;
    logic        href_active_d;
    logic        byte_pending;
    logic        frame_armed;
    logic        frame_seen;
    logic        line_had_data;
    logic [7:0]  first_byte;
    logic [15:0] x_count;
    logic [15:0] y_count;

    wire vsync_active = (cam_vsync == VSYNC_ACTIVE_LEVEL);
    wire href_active  = (cam_href == HREF_ACTIVE_LEVEL);
    wire vsync_start  = vsync_active && !vsync_active_d;
    wire href_stop    = !href_active && href_active_d;

    /**
     * Intent: Pair bytes and expose registered pixels and boundary events.
     * Invariant: `pixel_valid` is asserted only after a complete byte pair.
     * Hazard: An HREF window with an odd byte count reports an error and drops
     * the incomplete pixel at the window boundary.
     */
    always_ff @(posedge cam_pclk or negedge rst_n) begin
        if (!rst_n) begin
            vsync_active_d <= 1'b0;
            href_active_d  <= 1'b0;
            byte_pending   <= 1'b0;
            frame_armed    <= 1'b0;
            frame_seen     <= 1'b0;
            line_had_data  <= 1'b0;
            first_byte     <= 8'h00;
            x_count        <= 16'h0000;
            y_count        <= 16'h0000;
            pixel_valid    <= 1'b0;
            pixel_data     <= 16'h0000;
            frame_start    <= 1'b0;
            line_start     <= 1'b0;
            line_end       <= 1'b0;
            frame_end      <= 1'b0;
            pixel_x        <= 16'h0000;
            pixel_y        <= 16'h0000;
            protocol_error <= 1'b0;
        end else begin
            vsync_active_d <= vsync_active;
            href_active_d  <= href_active;
            pixel_valid    <= 1'b0;
            frame_start    <= 1'b0;
            line_start     <= 1'b0;
            line_end       <= 1'b0;
            frame_end      <= 1'b0;
            protocol_error <= 1'b0;

            if (vsync_start) begin
                frame_end     <= frame_seen;
                frame_armed   <= 1'b1;
                frame_seen    <= 1'b0;
                byte_pending  <= 1'b0;
                line_had_data <= 1'b0;
                x_count       <= 16'h0000;
                y_count       <= 16'h0000;
            end

            if (!href_active) begin
                if (byte_pending) begin
                    protocol_error <= 1'b1;
                    byte_pending   <= 1'b0;
                end
                if (href_stop) begin
                    line_end      <= line_had_data;
                    line_had_data <= 1'b0;
                    x_count       <= 16'h0000;
                    if (line_had_data) begin
                        if (&y_count) begin
                            protocol_error <= 1'b1;
                        end else begin
                            y_count <= y_count + 16'h0001;
                        end
                    end
                end
            end else if (!byte_pending) begin
                first_byte   <= cam_data;
                byte_pending <= 1'b1;
            end else begin
                pixel_valid <= 1'b1;
                pixel_data  <= FIRST_BYTE_IS_HIGH ? {first_byte, cam_data}
                                                   : {cam_data, first_byte};
                pixel_x     <= x_count;
                pixel_y     <= y_count;
                line_start  <= !line_had_data;
                frame_start <= (frame_armed || vsync_start) && !frame_seen;
                frame_armed <= 1'b0;
                frame_seen  <= 1'b1;
                line_had_data <= 1'b1;
                byte_pending  <= 1'b0;
                if (&x_count) begin
                    protocol_error <= 1'b1;
                end else begin
                    x_count <= x_count + 16'h0001;
                end
            end
        end
    end

endmodule

`default_nettype wire
