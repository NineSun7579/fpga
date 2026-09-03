`default_nettype none

/**
 * @file rgb565_word_skid_buffer.sv
 * @brief 吸收 camera-side word 输出与 staging adapter 之间的短突发。
 *
 * @details
 * 输入侧沿用 M3-A packer 的无背压脉冲，缓冲区最多保存两个 128-bit word
 * 及其事件。输出侧使用标准 valid/ready；缓冲区满且下游未接收时，新的
 * 输入 word 被丢弃并置位 sticky `overflow`。随后当前帧余下输入被丢弃，
 * 队尾注入一个空载错误帧尾；观测到原帧尾并等待该中止记录排队后，才从
 * 后续 `frame_start` 恢复接收。
 *
 * @par Interface contract
 * - 输入 `in_valid` 每个时钟最多提交一个 word；`in_ready` 仅用于诊断和
 *   上层 overflow 判断，不能为无背压的 packer 提供反向流控。丢帧期间
 *   `in_ready` 保持为 0，只有后续新帧满足恢复条件时才重新表示可接收。
 * - 输出在 `out_valid && out_ready` 时移出一个 word；未接收期间所有字段保持。
 * - 两个槽位按先入先出顺序保存；满队列同拍出队和入队时允许直接替换尾槽。
 * - `overflow` 异步复位清零，发生一次无法接收的输入后保持为 1。
 * - 溢出后输出唯一的 `keep=0/frame_end=1/protocol_error=1` 中止记录；该记录
 *   排在溢出前已保存的 word 之后。当前帧剩余输入被丢弃，直到看到其帧尾。
 * - 看到帧尾且中止记录已排队后，只有带 `frame_start` 的输入 word 才能恢复；
 *   过早到达的帧中段仍被丢弃，以免输出不完整新帧。
 * - 恢复依赖源端最终产生 `in_frame_end`；若该边界永久缺失，模块持续丢弃，
 *   直到 `rst_n` 被重新断言，不根据超时猜测帧边界。
 *
 * @par Clock and reset
 * - Clock: `clk`, rising edge.
 * - Reset: `rst_n`, asynchronous assertion; release behavior belongs to the
 *   integrating clock/reset design.
 *
 * @warning
 * 这是 board-independent 的短缓冲合同，不证明持续满载无丢帧，也不替代
 * DDR3 帧缓存或最终 CDC/RDC 复位审核。
 */
module rgb565_word_skid_buffer (
    input  wire logic         rst_n,
    input  wire logic         clk,
    input  wire logic         in_valid,
    output logic              in_ready,
    input  wire logic [127:0]  in_data,
    input  wire logic [15:0]   in_keep,
    input  wire logic          in_frame_start,
    input  wire logic          in_line_start,
    input  wire logic          in_line_end,
    input  wire logic          in_frame_end,
    input  wire logic          in_protocol_error,
    output logic              out_valid,
    input  wire logic          out_ready,
    output logic [127:0]       out_data,
    output logic [15:0]        out_keep,
    output logic               out_frame_start,
    output logic               out_line_start,
    output logic               out_line_end,
    output logic               out_frame_end,
    output logic               out_protocol_error,
    output logic               overflow
);
    logic [127:0] data_slot0, data_slot1;
    logic [15:0] keep_slot0, keep_slot1;
    logic [4:0] events_slot0, events_slot1;
    logic [1:0] count;
    logic        push, pop;
    logic        push_abort, push_normal, push_recovery;
    logic        queue_space;
    logic        drop_active;
    logic        abort_pending;
    logic        dropped_frame_end_seen;
    logic [127:0] push_data;
    logic [15:0]  push_keep;
    logic [4:0]   push_events;

    assign queue_space = (count < 2) || (out_ready && (count != 0));
    assign in_ready = queue_space &&
                      ((!drop_active && !abort_pending) ||
                       (drop_active && dropped_frame_end_seen &&
                        !abort_pending && in_frame_start));
    assign push_abort = abort_pending && queue_space;
    assign push_recovery = in_valid && in_ready && drop_active;
    assign push_normal = in_valid && in_ready && !drop_active;
    assign push = push_abort || push_normal || push_recovery;
    assign out_valid = (count != 0);
    assign pop = out_valid && out_ready;

    always_comb begin
        if (push_abort) begin
            push_data = 128'h0;
            push_keep = 16'h0;
            push_events = 5'b1_1_0_0_0;
        end else begin
            push_data = in_data;
            push_keep = in_keep;
            push_events = {in_protocol_error, in_frame_end,
                           in_line_end, in_line_start, in_frame_start};
        end
    end

    always_comb begin
        out_data = data_slot0;
        out_keep = keep_slot0;
        out_frame_start = events_slot0[0];
        out_line_start = events_slot0[1];
        out_line_end = events_slot0[2];
        out_frame_end = events_slot0[3];
        out_protocol_error = events_slot0[4];
    end

    // FSM: frame recovery control
    // Type: mixed flag-encoded control with registered state and combinational handshakes.
    // Encoding: user-defined `drop_active/abort_pending/dropped_frame_end_seen` flags.
    // Reset state: normal receive, no pending abort, no observed dropped-frame end.
    // Illegal-state policy: asynchronous reset returns to normal; no safety recovery claim.
    // Output timing: the synthetic abort is queued after retained words and follows FIFO timing.
    /**
     * Intent: Keep a shallow FIFO contract at the packer/adapter boundary and
     *          close a frame when camera-side pressure creates a data hole.
     * Invariant: `count` is the number of valid slots and never exceeds two.
     * Hazard: An input accepted while full is only legal when the head is
     * removed in the same cycle; otherwise it starts whole-frame dropping.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_slot0 <= 128'h0;
            data_slot1 <= 128'h0;
            keep_slot0 <= 16'h0;
            keep_slot1 <= 16'h0;
            events_slot0 <= 5'h0;
            events_slot1 <= 5'h0;
            count <= 2'd0;
            overflow <= 1'b0;
            drop_active <= 1'b0;
            abort_pending <= 1'b0;
            dropped_frame_end_seen <= 1'b0;
        end else begin
            if (in_valid && !drop_active && !queue_space) begin
                overflow <= 1'b1;
                drop_active <= 1'b1;
                abort_pending <= 1'b1;
                dropped_frame_end_seen <= in_frame_end;
            end else if (drop_active) begin
                if (in_valid && in_frame_end)
                    dropped_frame_end_seen <= 1'b1;
                if (push_abort)
                    abort_pending <= 1'b0;
                if (push_recovery) begin
                    drop_active <= 1'b0;
                    dropped_frame_end_seen <= 1'b0;
                end
            end

            case ({push, pop})
                2'b10: begin
                    if (count == 0) begin
                        data_slot0 <= push_data;
                        keep_slot0 <= push_keep;
                        events_slot0 <= push_events;
                    end else begin
                        data_slot1 <= push_data;
                        keep_slot1 <= push_keep;
                        events_slot1 <= push_events;
                    end
                    count <= count + 2'd1;
                end
                2'b01: begin
                    data_slot0 <= data_slot1;
                    keep_slot0 <= keep_slot1;
                    events_slot0 <= events_slot1;
                    count <= count - 2'd1;
                end
                2'b11: begin
                    if (count == 1) begin
                        data_slot0 <= push_data;
                        keep_slot0 <= push_keep;
                        events_slot0 <= push_events;
                    end else begin
                        data_slot0 <= data_slot1;
                        keep_slot0 <= keep_slot1;
                        events_slot0 <= events_slot1;
                        data_slot1 <= push_data;
                        keep_slot1 <= push_keep;
                        events_slot1 <= push_events;
                    end
                end
                default: begin
                end
            endcase
        end
    end
endmodule

`default_nettype wire
