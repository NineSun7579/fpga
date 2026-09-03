`default_nettype none

/**
 * @file rgb565_axis4_frame_read_scheduler.sv
 * @brief 为已提交帧顺序生成单 outstanding 的 DDR3 记录读命令。
 *
 * @details
 * 调度器消费包含槽号、首记录 opaque 地址、记录数和 committed 决策的帧描述符。
 * 不可提交描述符直接结束且不产生读命令；已提交描述符从首地址开始，每次
 * 只允许一个命令等待对应响应被后级接受，随后按 `ADDR_STEP` 推进。记录数
 * 与响应帧尾不一致时，当前响应被归一化为帧尾并报告 fault，避免读调度和
 * 下游帧窗口永久分裂。模块不解释地址单位、不接收 DDR 数据，也不实例化
 * 厂商 DDR3 或 PCIe IP。
 *
 * @par Interface contract
 * - `desc_valid && desc_ready` 接受一个帧描述符。
 * - 描述符槽号保持到当前帧完成，并与 `frame_done_pulse` 同周期输出。
 * - 已提交且记录数为零的描述符不发命令，并输出完成和 fault 脉冲。
 * - `read_cmd_valid && read_cmd_ready` 发出一条读命令；命令在背压期间保持。
 * - `read_response_ready` 表示当前响应可与已接受命令配对；支持命令和零延迟
 *   响应在同一周期握手。
 * - 每条已接受命令必须恰好对应一个 `read_response_accepted` 事件。
 * - 帧尾提前或最后计数响应缺少帧尾时，归一化帧尾、输出 fault 并结束当前帧。
 * - 正常或 fault 结束均输出一个周期的 `frame_done_pulse` 并返回空闲。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，低有效异步断言；集成层必须相对 `clk` 同步释放。
 *
 * @par Assumptions
 * - 描述符地址序列连续，下一记录地址等于当前地址加 `ADDR_STEP`。
 * - 集成层只为当前命令返回响应，且不丢失、不重复、不乱序。
 * - `ADDR_STEP` 非零，且 token 地址回绕策略由外部帧管理器约束。
 *
 * @warning
 * 本模块只定义 vendor-independent 读命令顺序和响应配对，不证明真实 DDR3
 * 地址映射、初始化、突发、仲裁、读延迟或数据持久化。
 */
module rgb565_axis4_frame_read_scheduler #(
    parameter logic [27:0] ADDR_STEP = 28'd1
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        desc_valid,
    output logic             desc_ready,
    input  wire logic        desc_slot_id,
    input  wire logic [27:0] desc_start_addr,
    input  wire logic [31:0] desc_records,
    input  wire logic        desc_committed,
    output logic             read_cmd_valid,
    input  wire logic        read_cmd_ready,
    output logic [27:0]      read_cmd_addr,
    input  wire logic        read_response_accepted,
    input  wire logic        read_response_frame_end,
    output logic             read_response_ready,
    output logic             read_response_frame_end_normalized,
    output logic             read_response_protocol_error,
    output logic             frame_done_pulse,
    output logic             frame_done_slot_id,
    output logic             frame_fault_pulse,
    output logic             active
);
    logic        active_reg;
    logic        response_outstanding_reg;
    logic [27:0] next_addr_reg;
    logic [31:0] records_left_reg;
    logic        command_accepted;
    logic        response_accepted;
    logic        expected_frame_end;

    always_comb begin
        desc_ready = !active_reg && !response_outstanding_reg;
        read_cmd_valid = active_reg && !response_outstanding_reg &&
                         (records_left_reg != 32'd0);
        read_cmd_addr = next_addr_reg;
        command_accepted = read_cmd_valid && read_cmd_ready;
        read_response_ready = active_reg &&
                              (response_outstanding_reg || command_accepted);
        response_accepted = read_response_accepted && read_response_ready;
        expected_frame_end = (records_left_reg == 32'd1);
        read_response_frame_end_normalized = read_response_ready &&
                                             (read_response_frame_end ||
                                              expected_frame_end);
        read_response_protocol_error = read_response_ready &&
                                       (read_response_frame_end !=
                                        expected_frame_end);
        active = active_reg;
    end

    /**
     * Intent: Serialize frame record reads so each command has one accepted response.
     * FSM: User-coded mixed Moore/Mealy state is the pair
     *      `active_reg/response_outstanding_reg`; command availability is Moore-style,
     *      while zero-latency response readiness also depends on command ready.
     * Encoding: `00` idle, `10` command available, `11` response outstanding;
     *           `01` is illegal, cannot be entered by defined transitions, and is
     *           cleared only by reset; target sign-off must detect illegal encoding.
     * Invariant: At most one read command can be outstanding.
     * Latency: The first command becomes visible after the descriptor sampling edge;
     *          the next command becomes visible after the prior response sampling edge;
     *          a zero-latency response may complete on its command sampling edge.
     * Hazard: A missing response stalls the current frame indefinitely; timeout and
     *         controller recovery belong to the integrating frame manager.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_reg               <= 1'b0;
            response_outstanding_reg <= 1'b0;
            next_addr_reg            <= 28'd0;
            records_left_reg         <= 32'd0;
            frame_done_pulse         <= 1'b0;
            frame_done_slot_id       <= 1'b0;
            frame_fault_pulse        <= 1'b0;
        end else begin
            frame_done_pulse <= 1'b0;
            frame_fault_pulse <= 1'b0;

            if (desc_valid && desc_ready) begin
                frame_done_slot_id       <= desc_slot_id;
                active_reg               <= desc_committed &&
                                            (desc_records != 32'd0);
                response_outstanding_reg <= 1'b0;
                next_addr_reg            <= desc_start_addr;
                records_left_reg         <= desc_committed ? desc_records : 32'd0;
                if (desc_committed && (desc_records == 32'd0)) begin
                    frame_done_pulse  <= 1'b1;
                    frame_fault_pulse <= 1'b1;
                end
            end else begin
                if (command_accepted) begin
                    response_outstanding_reg <= 1'b1;
                    next_addr_reg            <= next_addr_reg + ADDR_STEP;
                end

                if (response_accepted) begin
                    response_outstanding_reg <= 1'b0;
                    if (read_response_frame_end || expected_frame_end) begin
                        active_reg        <= 1'b0;
                        records_left_reg  <= 32'd0;
                        frame_done_pulse  <= 1'b1;
                        frame_fault_pulse <= read_response_protocol_error;
                    end else begin
                        records_left_reg <= records_left_reg - 32'd1;
                    end
                end
            end
        end
    end
endmodule

`default_nettype wire
