`default_nettype none

/**
 * @file rgb565_axis4_frame_readout_gate.sv
 * @brief 只将已提交帧的 DDR3 读回记录透传到 PCIe MWR 输入边界。
 *
 * @details
 * 该模块接收帧提交描述符和随后从 DDR3 读出的规范化记录。已提交帧才会
 * 打开读侧 ready 并透传记录；作废帧保持读侧关闭，同时产生一个单周期
 * `drop_frame_pulse`。模块不生成 DDR3 地址，不缓存整帧，也不实例化厂商
 * PCIe IP；实际存储和读出调度由集成层负责。
 *
 * @par Interface contract
 * - `desc_valid && desc_ready` 接受一个帧提交结果。
 * - `desc_committed=1` 后，读侧记录按照 ready/valid 原样透传。
 * - `desc_committed=0` 时不接受读侧记录，并在描述符接受后输出一个
 *   `drop_frame_pulse`。
 * - 已提交帧的 `read_frame_end` 记录完成握手后，下一周期关闭读侧。
 * - 输出记录在 `out_valid && out_ready` 前保持，字段来自读侧输入。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，异步断言；释放行为属于集成层责任。
 *
 * @par Assumptions
 * - 外部 DDR3 读出器可独立于 `read_ready` 拉高 `read_valid`；未完成握手时
 *   必须保持 `read_valid` 和全部记录字段稳定。
 * - 作废帧不得向本模块提供读记录；`drop_frame_pulse` 用于通知外部调度器
 *   回收该帧并推进到下一帧描述符。
 * - 已提交描述符对应的读出序列最终提供一个 `read_frame_end`。
 *
 * @warning
 * 该模块只实现帧完整性结果到读出使能的策略，不证明 DDR3 读时序、PCIe
 * TLP/DMA 或主机内存写入。
 */
module rgb565_axis4_frame_readout_gate (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        desc_valid,
    output logic             desc_ready,
    input  wire logic        desc_committed,
    input  wire logic        read_valid,
    output logic             read_ready,
    input  wire logic [31:0] read_data,
    input  wire logic [3:0]  read_keep,
    input  wire logic        read_last,
    input  wire logic        read_frame_end,
    input  wire logic        read_protocol_error,
    output logic             out_valid,
    input  wire logic         out_ready,
    output logic [31:0]      out_data,
    output logic [3:0]       out_keep,
    output logic             out_last,
    output logic             out_frame_end,
    output logic             out_protocol_error,
    output logic              drop_frame_pulse
);
    logic frame_active;

    always_comb begin
        desc_ready = !frame_active;
        read_ready = frame_active && out_ready;
        out_valid = frame_active && read_valid;
        out_data = read_data;
        out_keep = read_keep;
        out_last = read_last;
        out_frame_end = read_frame_end;
        out_protocol_error = read_protocol_error;
    end

    /**
     * Intent: Convert one frame commit decision into a bounded readout window.
     * FSM: One-bit user-coded Moore state (`frame_active`); read ready/valid are
     *      combinationally gated by that state, while `drop_frame_pulse` is a
     *      registered one-cycle response to an uncommitted descriptor handshake.
     * Illegal state: Both bit values are defined, so there is no unused encoding.
     * Invariant: An uncommitted frame cannot produce an output handshake.
     * Latency: A committed descriptor opens the window after its sampling edge;
     *          a frame-end record closes it after that record's handshake edge.
     * Hazard: A missing read-side frame end leaves the committed window active;
     *         timeout recovery belongs to the integrating frame manager.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_active <= 1'b0;
            drop_frame_pulse <= 1'b0;
        end else begin
            drop_frame_pulse <= 1'b0;
            if (desc_valid && desc_ready) begin
                frame_active <= desc_committed;
                if (!desc_committed)
                    drop_frame_pulse <= 1'b1;
            end else if (frame_active && read_valid && read_ready && read_frame_end) begin
                frame_active <= 1'b0;
            end
        end
    end
endmodule

`default_nettype wire
