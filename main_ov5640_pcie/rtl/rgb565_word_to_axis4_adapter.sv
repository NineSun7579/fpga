`default_nettype none

/**
 * @file rgb565_word_to_axis4_adapter.sv
 * @brief 将 M3-A 16-byte 图像字拆分为 4-byte AXIS staging beat。
 *
 * @details
 * 本模块只完成板级无关的字节宽度适配，不实例化 PCIe/DDR3 IP，也不定义
 * PCIe TLP 或主机地址协议。输入字的低 byte lane 先发送；一个完整 128-bit
 * 字最多产生四个 32-bit 有效片段。输入保持在寄存器中直到所有片段被接收。
 *
 * @par Interface contract
 * - `in_valid && in_ready` 接受一个 M3-A 图像字或空载控制事件。
 * - 非空字按 4-byte 片段输出，`out_keep` 只表示当前片段的四个 byte lane。
 * - `out_last` 在该输入字的最后一个片段拉高；输入字的事件不会跨字传播。
 * - `out_user[0]`/`[1]` 表示帧首/行首，附着在首个有效片段；`[2]`/`[3]`/`[4]`
 *   表示行尾/帧尾/协议错误，附着在最后一个有效片段。
 * - 无 payload 的控制事件输出一个 `out_keep=4'b0000`、`out_last=1` 的 beat。
 * - `out_data[31:0]` 是当前片段的有效数据；其余位为 0。
 *
 * @par Clock and reset
 * - Clock: `clk`, rising edge.
 * - Reset: `rst_n`, asynchronous assertion; release behavior belongs to the
 *   integrating clock/reset design.
 *
 * @warning
 * `out_keep` 的 4-bit 语义只适合作为 staging 接口；PCIe 厂商 `tuser` 编码、
 * 最大 payload、TLP 分段和主机协议仍需由后续集成合同定义。
 */
module rgb565_word_to_axis4_adapter (
    input  wire logic         rst_n,
    input  wire logic         clk,
    input  wire logic         in_valid,
    output logic              in_ready,
    input  wire logic [127:0] in_data,
    input  wire logic [15:0]  in_keep,
    input  wire logic         in_frame_start,
    input  wire logic         in_line_start,
    input  wire logic         in_line_end,
    input  wire logic         in_frame_end,
    input  wire logic         in_protocol_error,
    output logic              out_valid,
    input  wire logic         out_ready,
    output logic [127:0] out_data,
    output logic [3:0]   out_keep,
    output logic         out_last,
    output logic [7:0]   out_user
);

    logic         active;
    logic         control_only;
    logic [127:0] data_reg;
    logic [15:0]  keep_reg;
    logic [1:0]   beat_index;
    logic [1:0]   beat_count;
    logic [7:0]   user_reg;
    logic [3:0]   current_keep;
    logic [31:0]  current_data;

    function automatic logic [4:0] popcount16(input logic [15:0] value);
        integer index;
        begin
            popcount16 = 5'd0;
            for (index = 0; index < 16; index = index + 1) begin
                popcount16 = popcount16 + value[index];
            end
        end
    endfunction

    // Intent: Select one 4-byte slice while preserving M3-A low-lane ordering.
    always_comb begin
        case (beat_index)
            2'd0: begin current_data = data_reg[31:0]; current_keep = keep_reg[3:0]; end
            2'd1: begin current_data = data_reg[63:32]; current_keep = keep_reg[7:4]; end
            2'd2: begin current_data = data_reg[95:64]; current_keep = keep_reg[11:8]; end
            default: begin current_data = data_reg[127:96]; current_keep = keep_reg[15:12]; end
        endcase
    end

    always_comb begin
        // A terminal output beat may be replaced by the next input word in
        // the same cycle, preventing adjacent line/frame control events from
        // being dropped by the no-backpressure M3-A packer.
        in_ready  = !active || (active && out_ready &&
                    (control_only || (beat_index == beat_count)));
        out_valid = active;
        out_data  = 128'h0;
        out_keep  = 4'h0;
        out_last  = 1'b0;
        out_user  = 8'h0;
        if (active) begin
            out_data[31:0] = current_data;
            out_keep = control_only ? 4'h0 : current_keep;
            out_last = control_only || (beat_index == beat_count);
            if (beat_index == 2'd0) begin
                out_user[1:0] = user_reg[1:0];
            end
            if (control_only || (beat_index == beat_count)) begin
                out_user[4:2] = user_reg[4:2];
            end
        end
    end

    /**
     * Intent: Hold one input word while downstream applies backpressure.
     * Invariant: A non-empty word emits exactly `beat_count + 1` beats.
     * Hazard: Changing lane order changes the later PCIe payload byte sequence.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active       <= 1'b0;
            control_only <= 1'b0;
            data_reg     <= 128'h0;
            keep_reg     <= 16'h0;
            beat_index   <= 2'd0;
            beat_count   <= 2'd0;
            user_reg     <= 8'h0;
        end else if (in_valid && in_ready) begin
            active       <= 1'b1;
            control_only <= (in_keep == 16'h0);
            data_reg     <= in_data;
            keep_reg     <= in_keep;
            beat_index   <= 2'd0;
            if (in_keep == 16'h0) begin
                beat_count <= 2'd0;
            end else begin
                // Store the last beat index; 16 bytes therefore use index 3.
                beat_count <= ((popcount16(in_keep) + 5'd3) >> 2) - 2'd1;
            end
            user_reg     <= {3'b000, in_protocol_error, in_frame_end,
                             in_line_end, in_line_start, in_frame_start};
        end else if (active && out_ready) begin
            if (control_only || (beat_index == beat_count)) begin
                active <= 1'b0;
            end else begin
                beat_index <= beat_index + 2'd1;
            end
        end
    end

endmodule

`default_nettype wire
