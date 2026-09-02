`default_nettype none

/**
 * @file rgb565_grayscale.sv
 * @brief Convert a registered RGB565 pixel stream to grayscale RGB565.
 *
 * @details
 * The module applies the integer luma approximation
 * `Y=(77*R+150*G+29*B)>>8` after expanding RGB565 components to eight bits.
 * The resulting eight-bit value is replicated into the RGB565 fields. Stream
 * events, coordinates, and protocol errors are delayed by one `cam_pclk`.
 *
 * @par Interface contract
 * - `pixel_data`, coordinates, and events are sampled on the rising edge of
 *   `cam_pclk` when `pixel_valid` is asserted.
 * - Each accepted pixel produces one grayscale output pixel one clock later.
 * - `frame_start`, `line_start`, `line_end`, `frame_end`, and
 *   `protocol_error` preserve their input event meaning with the same one-clock
 *   latency. No backpressure is provided.
 * - `pixel_data` is zero when the delayed `out_valid` is low.
 *
 * @par Clock and reset
 * - Clock: `cam_pclk`, rising edge.
 * - Reset: `rst_n`, asynchronous assertion; release behavior is owned by the
 *   integrating clock/reset design.
 *
 * @par Assumptions
 * - The input stream and all event signals are synchronous to `cam_pclk`.
 * - RGB565 uses the conventional R[15:11], G[10:5], B[4:0] bit fields.
 *
 * @warning
 * Changing the luma coefficients or component expansion changes the observable
 * image data and must update the behavior test reference model.
 */
module rgb565_grayscale (
    input  wire logic        rst_n,
    input  wire logic        cam_pclk,
    input  wire logic        pixel_valid,
    input  wire logic [15:0] pixel_data,
    input  wire logic        frame_start,
    input  wire logic        line_start,
    input  wire logic        line_end,
    input  wire logic        frame_end,
    input  wire logic [15:0] pixel_x,
    input  wire logic [15:0] pixel_y,
    input  wire logic        protocol_error,
    output logic             out_valid,
    output logic [15:0]      out_data,
    output logic             out_frame_start,
    output logic             out_line_start,
    output logic             out_line_end,
    output logic             out_frame_end,
    output logic [15:0]      out_x,
    output logic [15:0]      out_y,
    output logic             out_protocol_error
);

    logic [7:0]  red_8;
    logic [7:0]  green_8;
    logic [7:0]  blue_8;
    logic [15:0] red_term;
    logic [15:0] green_term;
    logic [15:0] blue_term;
    logic [17:0] luma_sum;
    logic [7:0]  gray_8;
    logic [15:0] gray_565;

    // Intent: Keep coefficient arithmetic explicit so intermediate products
    // cannot be truncated by expression sizing rules.
    always_comb begin
        red_8     = {pixel_data[15:11], pixel_data[15:13]};
        green_8   = {pixel_data[10:5], pixel_data[10:9]};
        blue_8    = {pixel_data[4:0], pixel_data[4:2]};
        red_term  = {8'h00, red_8} * 16'd77;
        green_term = {8'h00, green_8} * 16'd150;
        blue_term = {8'h00, blue_8} * 16'd29;
        luma_sum  = {2'h0, red_term} + {2'h0, green_term} + {2'h0, blue_term};
        gray_8    = luma_sum[17:8];
        gray_565  = {gray_8[7:3], gray_8[7:2], gray_8[7:3]};
    end

    /**
     * Intent: Register the processed stream and preserve event alignment.
     * Invariant: Every output event corresponds to the input event from the
     * immediately preceding cam_pclk cycle.
     * Hazard: Adding a second register here requires all downstream frame
     * protocol and latency checks to be updated.
     */
    always_ff @(posedge cam_pclk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid          <= 1'b0;
            out_data           <= 16'h0000;
            out_frame_start    <= 1'b0;
            out_line_start     <= 1'b0;
            out_line_end       <= 1'b0;
            out_frame_end      <= 1'b0;
            out_x              <= 16'h0000;
            out_y              <= 16'h0000;
            out_protocol_error <= 1'b0;
        end else begin
            out_valid          <= pixel_valid;
            out_data           <= pixel_valid ? gray_565 : 16'h0000;
            out_frame_start    <= frame_start;
            out_line_start     <= line_start;
            out_line_end       <= line_end;
            out_frame_end      <= frame_end;
            out_x              <= pixel_x;
            out_y              <= pixel_y;
            out_protocol_error <= protocol_error;
        end
    end

endmodule

`default_nettype wire
