`default_nettype none

/**
 * @file rgb565_axis4_frame_accounting.sv
 * @brief 在 staging beat 流上生成板级无关的帧统计描述符。
 *
 * @details
 * 本模块只统计有效 byte 数、beat 数和协议错误，并在帧尾产生一个固定格式
 * 描述符；不定义 DDR3 地址、PCIe TLP 或主机寄存器协议。输入 beat 必须来自
 * `rgb565_word_to_axis4_adapter`，其 keep 为连续低位有效 lane。
 *
 * @par Interface contract
 * - `in_valid && in_ready` 接受一个 staging beat，`in_keep` 的 1 bit 表示 1 byte。
 * - `in_user[3]` 表示帧尾，`in_user[4]` 表示协议错误；控制 beat 可完成空帧。
 * - 帧尾 beat 被接受后，下一拍最多产生一个 `desc_valid`。
 * - 描述符包含本帧有效字节数、已接收 beat 数和累计协议错误。
 * - 描述符未被接收时保持输出，阻塞新的输入帧。
 *
 * @par Clock and reset
 * - Clock: `clk`, rising edge.
 * - Reset: `rst_n`, asynchronous assertion; release behavior belongs to integration.
 */
module rgb565_axis4_frame_accounting (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        in_valid,
    output logic             in_ready,
    input  wire logic [3:0]  in_keep,
    input  wire logic [4:0]  in_user,
    output logic             desc_valid,
    input  wire logic        desc_ready,
    output logic [31:0]      desc_bytes,
    output logic [31:0]      desc_beats,
    output logic             desc_protocol_error
);
    logic [31:0] byte_count;
    logic [31:0] beat_count;
    logic        error_seen;
    logic [2:0]  keep_bytes;

    always_comb begin
        keep_bytes = {2'b0, in_keep[0]} + {2'b0, in_keep[1]} +
                     {2'b0, in_keep[2]} + {2'b0, in_keep[3]};
        in_ready = !desc_valid;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byte_count          <= 32'd0;
            beat_count          <= 32'd0;
            error_seen          <= 1'b0;
            desc_valid          <= 1'b0;
            desc_bytes          <= 32'd0;
            desc_beats          <= 32'd0;
            desc_protocol_error <= 1'b0;
        end else begin
            if (desc_valid && desc_ready) begin
                desc_valid <= 1'b0;
            end
            if (in_valid && in_ready) begin
                if (in_user[3]) begin
                    desc_valid          <= 1'b1;
                    desc_bytes          <= byte_count + keep_bytes;
                    desc_beats          <= beat_count + ((in_keep != 4'h0) ? 32'd1 : 32'd0);
                    desc_protocol_error <= error_seen | in_user[4];
                    byte_count          <= 32'd0;
                    beat_count          <= 32'd0;
                    error_seen          <= 1'b0;
                end else begin
                    byte_count <= byte_count + keep_bytes;
                    beat_count <= beat_count + ((in_keep != 4'h0) ? 32'd1 : 32'd0);
                    error_seen <= error_seen | in_user[4];
                end
            end
        end
    end
endmodule

`default_nettype wire
