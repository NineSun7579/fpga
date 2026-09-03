`default_nettype none

/**
 * @file rgb565_axis4_frame_commit.sv
 * @brief 将规范化 DDR3 记录聚合为帧提交或帧作废描述符。
 *
 * @details
 * 本模块位于 DDR3 记录读回与后续 PCIe 发送策略之间，只观察每条记录的
 * 有效字节数、帧尾和协议错误。帧尾被接受后产生一个保持型描述符；没有
 * 协议错误的帧标记为 `committed`，带错误的帧标记为不可提交。模块不生成
 * DDR3 物理地址，不解释控制器 burst，也不驱动厂商 PCIe IP。
 *
 * @par Interface contract
 * - `in_valid && in_ready` 接受一条规范化 DDR3 记录。
 * - `in_keep` 的每个置位表示一字节有效数据；空载控制记录仍计入 `records`。
 * - `in_frame_end` 接受后，当前帧的 `bytes`、`records` 和错误状态锁存到描述符。
 * - 描述符在 `desc_valid && desc_ready` 前保持稳定，并阻塞下一帧输入。
 * - `desc_committed` 仅在当前帧没有任何协议错误时为 1。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，异步断言；释放行为属于集成层责任。
 *
 * @par Assumptions
 * - 输入记录按帧顺序到达，且每个有效帧最终提供一个 `in_frame_end`。
 * - 单帧有效字节数和记录数可由 32-bit 统计字段表示。
 *
 * @warning
 * `desc_committed` 只是帧完整性策略结果，不等同于 DDR3 写入持久化或
 * PCIe 主机内存写入完成；后续读出器必须依据该字段决定是否发送帧。
 */
module rgb565_axis4_frame_commit (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        in_valid,
    output logic             in_ready,
    input  wire logic [3:0]  in_keep,
    input  wire logic        in_frame_end,
    input  wire logic        in_protocol_error,
    output logic             desc_valid,
    input  wire logic        desc_ready,
    output logic [31:0]      desc_bytes,
    output logic [31:0]      desc_records,
    output logic             desc_protocol_error,
    output logic             desc_committed
);
    logic [31:0] byte_count_reg;
    logic [31:0] record_count_reg;
    logic        error_seen_reg;
    logic [2:0]  keep_bytes;
    logic        frame_error;

    always_comb begin
        keep_bytes = {2'b0, in_keep[0]} + {2'b0, in_keep[1]} +
                     {2'b0, in_keep[2]} + {2'b0, in_keep[3]};
        frame_error = error_seen_reg | in_protocol_error;
        in_ready = !desc_valid;
    end

    /**
     * Intent: Commit only complete frames and preserve the decision while the
     *          downstream frame reader is backpressured.
     * Invariant: A descriptor describes exactly the records accepted since the
     *            previous frame-end record.
     * Hazard: A missing frame-end keeps the current counters open indefinitely;
     *         timeout recovery belongs to the integrating frame manager.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byte_count_reg      <= 32'd0;
            record_count_reg    <= 32'd0;
            error_seen_reg      <= 1'b0;
            desc_valid          <= 1'b0;
            desc_bytes          <= 32'd0;
            desc_records        <= 32'd0;
            desc_protocol_error <= 1'b0;
            desc_committed      <= 1'b0;
        end else begin
            if (desc_valid && desc_ready)
                desc_valid <= 1'b0;

            if (in_valid && in_ready) begin
                if (in_frame_end) begin
                    desc_valid          <= 1'b1;
                    desc_bytes          <= byte_count_reg + keep_bytes;
                    desc_records        <= record_count_reg + 32'd1;
                    desc_protocol_error <= frame_error;
                    desc_committed      <= !frame_error;
                    byte_count_reg      <= 32'd0;
                    record_count_reg    <= 32'd0;
                    error_seen_reg      <= 1'b0;
                end else begin
                    byte_count_reg   <= byte_count_reg + keep_bytes;
                    record_count_reg <= record_count_reg + 32'd1;
                    error_seen_reg   <= error_seen_reg | in_protocol_error;
                end
            end
        end
    end
endmodule

`default_nettype wire
