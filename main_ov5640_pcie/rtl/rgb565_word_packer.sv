`default_nettype none

/**
 * @file rgb565_word_packer.sv
 * @brief 将 RGB565 像素流组织为 128-bit 数据字。
 *
 * @details
 * 本模块只负责同一时钟域内的像素累积和字节有效标记，不负责传感器配置、
 * CDC、DDR3 事务、PCIe TLP 或主机地址。第一个像素放在输出字的低 16 bit，
 * 输出保留一个待发送完整字，以允许输入像素连续到达。
 *
 * @par Interface contract
 * - 输入每拍最多接受一个 `in_valid` 像素，不提供输入背压。
 * - 8 个像素形成一个 `word_valid` 输出字，像素 0 位于 `word_data[15:0]`。
 * - `word_keep` 的低 2N 位表示 N 个有效像素的 2N 个 byte lane。
 * - `word_frame_start` 和 `word_line_start` 随包含首像素的输出字输出。
 * - 行尾到达时，未满 8 个像素的字会补零输出；没有数据时输出控制事件。
 * - 帧尾和协议错误在有待发送数据时附着到该字，否则输出控制事件。
 *
 * @par Clock and reset
 * - Clock: `clk`, rising edge.
 * - Reset: `rst_n`, asynchronous assertion; release behavior belongs to the
 *   integrating clock/reset design.
 *
 * @warning
 * `word_data` 的字节序只定义本模块内部 128-bit 数据布局，不等同于厂商
 * PCIe AXIS 的 `tkeep` 或主机内存字节序；适配层必须另行定义转换规则。
 */
module rgb565_word_packer (
    input  wire logic         rst_n,
    input  wire logic         clk,
    input  wire logic         in_valid,
    input  wire logic [15:0]  in_data,
    input  wire logic         in_frame_start,
    input  wire logic         in_line_start,
    input  wire logic         in_line_end,
    input  wire logic         in_frame_end,
    input  wire logic         in_protocol_error,
    output logic              word_valid,
    output logic [127:0]      word_data,
    output logic [15:0]       word_keep,
    output logic              word_frame_start,
    output logic              word_line_start,
    output logic              word_line_end,
    output logic              word_frame_end,
    output logic              word_protocol_error
);

    logic [127:0] assembly_data;
    logic [2:0]   pixel_count;
    logic         assembly_frame_start;
    logic         assembly_line_start;
    logic         assembly_protocol_error;

    logic         pending_valid;
    logic [127:0] pending_data;
    logic [15:0]  pending_keep;
    logic         pending_frame_start;
    logic         pending_line_start;
    logic         pending_protocol_error;
    logic [127:0] assembly_with_input;

    function automatic logic [15:0] keep_for_pixels(input logic [2:0] count);
        case (count)
            3'd0: keep_for_pixels = 16'h0000;
            3'd1: keep_for_pixels = 16'h0003;
            3'd2: keep_for_pixels = 16'h000f;
            3'd3: keep_for_pixels = 16'h003f;
            3'd4: keep_for_pixels = 16'h00ff;
            3'd5: keep_for_pixels = 16'h03ff;
            3'd6: keep_for_pixels = 16'h0fff;
            3'd7: keep_for_pixels = 16'h3fff;
            default: keep_for_pixels = 16'hffff;
        endcase
    endfunction

    // Intent: Make variable pixel placement explicit and preserve the first
    // pixel in the least-significant 16-bit lane.
    always_comb begin
        assembly_with_input = assembly_data;
        assembly_with_input[pixel_count * 16 +: 16] = in_data;
    end

    /**
     * Intent: Register one complete word so the input path can accept one
     * pixel per clock while the output path emits one word per eight pixels.
     * Invariant: `pending_valid` contains exactly one complete eight-pixel word.
     * Hazard: A control event that arrives after the pending word has already
     * been emitted is represented as a control-only output event.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            assembly_data          <= 128'h0;
            pixel_count            <= 3'd0;
            assembly_frame_start   <= 1'b0;
            assembly_line_start    <= 1'b0;
            assembly_protocol_error <= 1'b0;
            pending_valid          <= 1'b0;
            pending_data           <= 128'h0;
            pending_keep           <= 16'h0;
            pending_frame_start    <= 1'b0;
            pending_line_start     <= 1'b0;
            pending_protocol_error <= 1'b0;
            word_valid             <= 1'b0;
            word_data              <= 128'h0;
            word_keep              <= 16'h0;
            word_frame_start       <= 1'b0;
            word_line_start        <= 1'b0;
            word_line_end          <= 1'b0;
            word_frame_end         <= 1'b0;
            word_protocol_error    <= 1'b0;
        end else begin
            word_valid          <= 1'b0;
            word_data           <= 128'h0;
            word_keep           <= 16'h0;
            word_frame_start    <= 1'b0;
            word_line_start     <= 1'b0;
            word_line_end       <= 1'b0;
            word_frame_end      <= 1'b0;
            word_protocol_error <= 1'b0;

            if (pending_valid) begin
                word_valid          <= 1'b1;
                word_data           <= pending_data;
                word_keep           <= pending_keep;
                word_frame_start    <= pending_frame_start;
                word_line_start     <= pending_line_start;
                word_line_end       <= in_line_end;
                word_frame_end      <= in_frame_end;
                word_protocol_error <= pending_protocol_error;
                if (in_protocol_error) begin
                    word_protocol_error <= 1'b1;
                end
                pending_valid       <= 1'b0;
            end else if ((in_line_end || in_frame_end) && (pixel_count != 3'd0)) begin
                word_valid          <= 1'b1;
                word_data           <= assembly_data;
                word_keep           <= keep_for_pixels(pixel_count);
                word_frame_start    <= assembly_frame_start;
                word_line_start     <= assembly_line_start;
                word_line_end       <= in_line_end;
                word_frame_end      <= in_frame_end;
                word_protocol_error <= assembly_protocol_error | in_protocol_error;
                assembly_data          <= 128'h0;
                pixel_count            <= 3'd0;
                assembly_frame_start   <= 1'b0;
                assembly_line_start    <= 1'b0;
                assembly_protocol_error <= 1'b0;
            end else if (in_line_end || in_frame_end || in_protocol_error) begin
                word_valid          <= 1'b1;
                word_line_end       <= in_line_end;
                word_frame_end      <= in_frame_end;
                word_protocol_error <= in_protocol_error;
            end

            if (in_valid) begin
                if (pixel_count == 3'd0) begin
                    assembly_frame_start    <= in_frame_start;
                    assembly_line_start     <= in_line_start;
                    assembly_protocol_error <= in_protocol_error;
                end else begin
                    assembly_protocol_error <= assembly_protocol_error |
                                                in_protocol_error;
                end

                if (pixel_count == 3'd7) begin
                    pending_valid          <= 1'b1;
                    pending_data           <= assembly_with_input;
                    pending_keep           <= 16'hffff;
                    pending_frame_start    <= assembly_frame_start;
                    pending_line_start     <= assembly_line_start;
                    pending_protocol_error <= assembly_protocol_error |
                                               in_protocol_error;
                    assembly_data          <= 128'h0;
                    pixel_count            <= 3'd0;
                    assembly_frame_start   <= 1'b0;
                    assembly_line_start    <= 1'b0;
                    assembly_protocol_error <= 1'b0;
                end else begin
                    assembly_data <= assembly_with_input;
                    pixel_count   <= pixel_count + 3'd1;
                end
            end
        end
    end

endmodule

`default_nettype wire
