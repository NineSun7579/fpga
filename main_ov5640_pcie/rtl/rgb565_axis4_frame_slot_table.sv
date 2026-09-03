`default_nettype none

/**
 * @file rgb565_axis4_frame_slot_table.sv
 * @brief 管理两个帧槽的写分配、提交排队和读完成回收。
 *
 * @details
 * 模块把两个固定槽基 token 作为写分配描述符输出。写侧完成一帧后提交槽号、
 * 首 token 和统计字段；可提交帧按完成顺序进入深度 2 FIFO，错误帧立即释放
 * 原槽并产生带槽号 drop 事件。读描述符被接受后槽进入 READING，只有携带
 * 匹配槽号的 `read_done_pulse` 才能释放。模块不存储图像数据，也不解释 token
 * 的 DDR3 物理单位。
 *
 * @par Interface contract
 * - `write_alloc_valid && write_alloc_ready` 把一个 FREE 槽转为 WRITING；分配字段
 *   在背压期间保持稳定。
 * - `commit_valid && commit_ready` 只接受 WRITING 槽的完成描述符，且首 token
 *   必须等于该槽固定基 token。
 * - committed 且无协议错误的描述符进入 FIFO，槽转为 QUEUED。
 * - 零记录、超过 `SLOT_RECORD_CAPACITY` 或 committed/error 决策矛盾的描述符
 *   作为 fault 帧释放，不进入 FIFO。
 * - 不可提交帧不进入 FIFO，槽转为 FREE，并输出一个周期的 drop 事件和槽号。
 * - `read_desc_valid && read_desc_ready` 按提交顺序输出描述符，槽转为 READING；
 *   当前读槽完成前不会暴露第二个读描述符。
 * - `read_done_pulse` 只释放匹配的 READING 槽；生命周期不匹配只报告 fault。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，低有效异步断言；集成层必须相对 `clk` 同步释放。
 *
 * @par Parameters
 * - `SLOT0_BASE_ADDR`、`SLOT1_BASE_ADDR`：两个槽的 opaque 首 token，必须不同。
 * - `SLOT_RECORD_CAPACITY`：每槽最多允许的记录数，必须大于零。
 *
 * @par Assumptions
 * - 每个已分配槽最终恰好提交一次；缺失 commit 的超时恢复属于上层帧管理器。
 * - 同一槽不会在同一周期收到多个合法生命周期事件。
 *
 * @warning
 * 该模块只实现双槽控制面，不证明 DDR3 容量、地址单位、持久化、仲裁、刷新、
 * PCIe DMA/TLP 或主机已经完成对应帧的接收。
 */
module rgb565_axis4_frame_slot_table #(
    parameter logic [27:0] SLOT0_BASE_ADDR = 28'd0,
    parameter logic [27:0] SLOT1_BASE_ADDR = 28'd1,
    parameter logic [31:0] SLOT_RECORD_CAPACITY = 32'hffff_ffff
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    output logic             write_alloc_valid,
    input  wire logic        write_alloc_ready,
    output logic             write_alloc_slot_id,
    output logic [27:0]      write_alloc_base_addr,
    input  wire logic        commit_valid,
    output logic             commit_ready,
    input  wire logic        commit_slot_id,
    input  wire logic [27:0] commit_start_addr,
    input  wire logic [31:0] commit_bytes,
    input  wire logic [31:0] commit_records,
    input  wire logic        commit_protocol_error,
    input  wire logic        commit_committed,
    output logic             read_desc_valid,
    input  wire logic        read_desc_ready,
    output logic             read_desc_slot_id,
    output logic [27:0]      read_desc_start_addr,
    output logic [31:0]      read_desc_bytes,
    output logic [31:0]      read_desc_records,
    output logic             read_desc_protocol_error,
    input  wire logic        read_done_pulse,
    input  wire logic        read_done_slot_id,
    output logic             drop_frame_pulse,
    output logic             drop_slot_id,
    output logic             fault_pulse
);
    typedef enum logic [1:0] {
        SLOT_FREE,
        SLOT_WRITING,
        SLOT_QUEUED,
        SLOT_READING
    } slot_state_t;

    slot_state_t slot0_state_reg;
    slot_state_t slot1_state_reg;

    logic        alloc_pending_reg;
    logic        alloc_slot_id_reg;
    logic [27:0] alloc_base_addr_reg;
    logic        reader_active_reg;
    logic        reader_slot_id_reg;

    logic        queue_slot_id [0:1];
    logic [27:0] queue_start_addr [0:1];
    logic [31:0] queue_bytes [0:1];
    logic [31:0] queue_records [0:1];
    logic        queue_protocol_error [0:1];
    logic        queue_head_reg;
    logic        queue_tail_reg;
    logic [1:0]  queue_count_reg;

    logic        commit_slot_writing;
    logic [27:0] commit_expected_addr;
    logic        commit_owner_valid;
    logic        commit_policy_mismatch;
    logic        commit_descriptor_fault;
    logic        commit_effective;
    logic        commit_accepted;
    logic        queue_push;
    logic        queue_pop;
    logic        queue_head_slot_queued;

    initial begin : p_validate_parameters
        if (SLOT0_BASE_ADDR == SLOT1_BASE_ADDR)
            $fatal(1, "frame slot base tokens must be different");
        if (SLOT_RECORD_CAPACITY == 32'd0)
            $fatal(1, "frame slot record capacity must be non-zero");
    end

    always_comb begin
        write_alloc_valid = alloc_pending_reg;
        write_alloc_slot_id = alloc_slot_id_reg;
        write_alloc_base_addr = alloc_base_addr_reg;

        commit_slot_writing = commit_slot_id ?
                              (slot1_state_reg == SLOT_WRITING) :
                              (slot0_state_reg == SLOT_WRITING);
        commit_expected_addr = commit_slot_id ? SLOT1_BASE_ADDR : SLOT0_BASE_ADDR;
        commit_owner_valid = commit_slot_writing &&
                             (commit_start_addr == commit_expected_addr);
        commit_policy_mismatch = (commit_committed == commit_protocol_error);
        commit_descriptor_fault = commit_policy_mismatch ||
                                  (commit_records == 32'd0) ||
                                  (commit_records > SLOT_RECORD_CAPACITY);
        commit_effective = commit_committed && !commit_protocol_error &&
                           !commit_descriptor_fault;
        queue_head_slot_queued = queue_slot_id[queue_head_reg] ?
                                 (slot1_state_reg == SLOT_QUEUED) :
                                 (slot0_state_reg == SLOT_QUEUED);
        queue_pop = (queue_count_reg != 2'd0) && !reader_active_reg &&
                    queue_head_slot_queued && read_desc_ready;
        commit_ready = !commit_owner_valid || !commit_effective ||
                       (queue_count_reg != 2'd2) || queue_pop;
        commit_accepted = commit_valid && commit_ready;
        queue_push = commit_accepted && commit_owner_valid && commit_effective;

        read_desc_valid = (queue_count_reg != 2'd0) && !reader_active_reg &&
                          queue_head_slot_queued;
        read_desc_slot_id = 1'b0;
        read_desc_start_addr = 28'd0;
        read_desc_bytes = 32'd0;
        read_desc_records = 32'd0;
        read_desc_protocol_error = 1'b0;
        if (queue_count_reg != 2'd0) begin
            read_desc_slot_id = queue_slot_id[queue_head_reg];
            read_desc_start_addr = queue_start_addr[queue_head_reg];
            read_desc_bytes = queue_bytes[queue_head_reg];
            read_desc_records = queue_records[queue_head_reg];
            read_desc_protocol_error = queue_protocol_error[queue_head_reg];
        end
    end

    /**
     * Intent: Maintain slot ownership and committed descriptor order.
     * FSM: Two independent four-state Moore slot machines, one registered reader
     *      owner, and a depth-2 FIFO; allocation/event pulses are registered while
     *      descriptor outputs are combinational views of registered state.
     * Encoding: tool-selected enum encoding; all four values are defined.
     * Illegal-state policy: no RTL recovery is claimed; target lint/synthesis and
     *                       fault injection must verify illegal encoding handling.
     * Invariant: A slot is offered only while FREE, at most one slot is READING,
     *            and release occurs only from WRITING by drop or from READING by
     *            completion matching the registered reader slot.
     * Latency: A newly free slot becomes a held allocation offer after a clock edge.
     * Hazard: Missing commit/read-done retains slot ownership indefinitely; timeout
     *         and system-level recovery belong to the integrating frame manager.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            slot0_state_reg       <= SLOT_FREE;
            slot1_state_reg       <= SLOT_FREE;
            alloc_pending_reg     <= 1'b0;
            alloc_slot_id_reg     <= 1'b0;
            alloc_base_addr_reg   <= 28'd0;
            reader_active_reg     <= 1'b0;
            reader_slot_id_reg    <= 1'b0;
            queue_head_reg        <= 1'b0;
            queue_tail_reg        <= 1'b0;
            queue_count_reg       <= 2'd0;
            drop_frame_pulse      <= 1'b0;
            drop_slot_id          <= 1'b0;
            fault_pulse           <= 1'b0;
        end else begin
            drop_frame_pulse <= 1'b0;
            fault_pulse <= 1'b0;

            if (!alloc_pending_reg) begin
                if (slot0_state_reg == SLOT_FREE) begin
                    alloc_pending_reg   <= 1'b1;
                    alloc_slot_id_reg   <= 1'b0;
                    alloc_base_addr_reg <= SLOT0_BASE_ADDR;
                end else if (slot1_state_reg == SLOT_FREE) begin
                    alloc_pending_reg   <= 1'b1;
                    alloc_slot_id_reg   <= 1'b1;
                    alloc_base_addr_reg <= SLOT1_BASE_ADDR;
                end
            end else if (write_alloc_ready) begin
                alloc_pending_reg <= 1'b0;
                if (alloc_slot_id_reg)
                    slot1_state_reg <= SLOT_WRITING;
                else
                    slot0_state_reg <= SLOT_WRITING;
            end

            if (queue_push) begin
                queue_slot_id[queue_tail_reg] <= commit_slot_id;
                queue_start_addr[queue_tail_reg] <= commit_start_addr;
                queue_bytes[queue_tail_reg] <= commit_bytes;
                queue_records[queue_tail_reg] <= commit_records;
                queue_protocol_error[queue_tail_reg] <= commit_protocol_error;
                queue_tail_reg <= queue_tail_reg + 1'b1;
                if (commit_slot_id)
                    slot1_state_reg <= SLOT_QUEUED;
                else
                    slot0_state_reg <= SLOT_QUEUED;
            end else if (commit_accepted && commit_owner_valid) begin
                if (commit_slot_id)
                    slot1_state_reg <= SLOT_FREE;
                else
                    slot0_state_reg <= SLOT_FREE;
                drop_frame_pulse <= 1'b1;
                drop_slot_id <= commit_slot_id;
                if (commit_descriptor_fault)
                    fault_pulse <= 1'b1;
            end else if (commit_accepted) begin
                fault_pulse <= 1'b1;
            end

            if (queue_pop) begin
                queue_head_reg <= queue_head_reg + 1'b1;
                reader_active_reg <= 1'b1;
                reader_slot_id_reg <= queue_slot_id[queue_head_reg];
                if (queue_slot_id[queue_head_reg]) begin
                    if (slot1_state_reg == SLOT_QUEUED)
                        slot1_state_reg <= SLOT_READING;
                    else
                        fault_pulse <= 1'b1;
                end else begin
                    if (slot0_state_reg == SLOT_QUEUED)
                        slot0_state_reg <= SLOT_READING;
                    else
                        fault_pulse <= 1'b1;
                end
            end

            case ({queue_push, queue_pop})
                2'b10: queue_count_reg <= queue_count_reg + 2'd1;
                2'b01: queue_count_reg <= queue_count_reg - 2'd1;
                default: queue_count_reg <= queue_count_reg;
            endcase

            if (read_done_pulse) begin
                if (reader_active_reg &&
                    (read_done_slot_id == reader_slot_id_reg)) begin
                    if (read_done_slot_id &&
                        (slot1_state_reg == SLOT_READING)) begin
                        slot1_state_reg <= SLOT_FREE;
                        reader_active_reg <= 1'b0;
                    end else if (!read_done_slot_id &&
                                 (slot0_state_reg == SLOT_READING)) begin
                        slot0_state_reg <= SLOT_FREE;
                        reader_active_reg <= 1'b0;
                    end else begin
                        fault_pulse <= 1'b1;
                    end
                end else begin
                    fault_pulse <= 1'b1;
                end
            end
        end
    end
endmodule

`default_nettype wire
