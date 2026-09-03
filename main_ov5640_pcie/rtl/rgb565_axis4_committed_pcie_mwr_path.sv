`default_nettype none

/**
 * @file rgb565_axis4_committed_pcie_mwr_path.sv
 * @brief 串接双槽帧提交、DDR3 读调度和规范化 PCIe MWR 路径。
 *
 * @details
 * 模块向写侧分配两个固定帧槽。已经写入 DDR3 记录模型的记录先由 frame
 * commit 聚合成带槽描述符，再进入双槽 committed FIFO。队首正常帧原子交给
 * 单 outstanding 读调度和读出门控，返回记录随后进入 PCIe MWR 路径。错误帧
 * 直接带槽作废；正常或恢复性 fault 完成携带槽号回收当前 READING 槽。
 * 模块不保存图像数据、不解释 DDR3 token 物理单位，也不实例化厂商 IP。
 *
 * @par Interface contract
 * - `write_alloc_*` 为外部 writer 提供保持型帧槽分配描述符。
 * - `commit_*` 必须描述已被 DDR3 写侧接受的记录，并携带该帧分配的 slot ID。
 * - frame commit 的描述符完整进入 slot table 后，writer 才可能复用已释放槽。
 * - 两个 committed 帧可排队，但任一时刻最多一个槽处于 READING。
 * - 每条读命令必须对应一条保持到 `read_valid && read_ready` 的记录。
 * - 错误帧输出 `drop_frame_pulse/drop_slot_id`，不产生读命令或 MWR。
 * - 正常或读协议 fault 完成输出 `frame_done_pulse/frame_done_slot_id`；读协议
 *   fault 和槽生命周期 fault 通过 `frame_fault_pulse` 汇总。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，低有效异步断言；集成层必须相对 `clk` 同步释放。
 *
 * @par Assumptions
 * - writer 与本模块位于同一时钟域，并把 allocation 字段原样绑定到 commit 记录。
 * - `SLOT0_BASE_ADDR`、`SLOT1_BASE_ADDR`、容量和步长定义的 token 区域不重叠。
 * - 外部读模型只返回当前已接受命令对应的记录，不丢失、不重复、不乱序。
 *
 * @warning
 * 这是 vendor-independent 行为连接层，不证明真实 DDR3 持久化、PCIe TLP/DMA、
 * 链路训练、主机内存写入或板级时序。
 */
module rgb565_axis4_committed_pcie_mwr_path #(
    parameter logic [63:0] BASE_ADDR = 64'd0,
    parameter logic [27:0] TOKEN_ADDR_STEP = 28'd1,
    parameter logic [27:0] SLOT0_BASE_ADDR = 28'd0,
    parameter logic [27:0] SLOT1_BASE_ADDR = 28'd1024,
    parameter logic [31:0] SLOT_RECORD_CAPACITY = 32'd1024
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    output logic             write_alloc_valid,
    input  wire logic        write_alloc_ready,
    output logic             write_alloc_slot_id,
    output logic [27:0]      write_alloc_base_addr,
    output logic [31:0]      write_alloc_record_capacity,
    input  wire logic        commit_valid,
    output logic             commit_ready,
    input  wire logic        commit_slot_id,
    input  wire logic [27:0] commit_addr,
    input  wire logic [3:0]  commit_keep,
    input  wire logic        commit_frame_end,
    input  wire logic        commit_protocol_error,
    output logic             read_cmd_valid,
    input  wire logic        read_cmd_ready,
    output logic [27:0]      read_cmd_addr,
    input  wire logic        read_valid,
    output logic             read_ready,
    input  wire logic [31:0] read_data,
    input  wire logic [3:0]  read_keep,
    input  wire logic        read_last,
    input  wire logic        read_frame_end,
    input  wire logic        read_protocol_error,
    output logic             drop_frame_pulse,
    output logic             drop_slot_id,
    output logic             frame_done_pulse,
    output logic             frame_done_slot_id,
    output logic             frame_fault_pulse,
    output logic             mwr32_req,
    input  wire logic        mwr32_req_ack,
    output logic [9:0]       req_length,
    output logic [63:0]      req_addr,
    output logic [31:0]      req_data,
    output logic [3:0]       req_keep,
    output logic             cross_4kb_boundary,
    output logic             req_last,
    output logic             req_frame_end,
    output logic             req_protocol_error,
    output logic             busy
);
    logic        frame_desc_valid;
    logic        frame_desc_ready;
    logic        frame_desc_slot_id;
    logic [27:0] frame_desc_start_addr;
    logic [31:0] frame_desc_bytes;
    logic [31:0] frame_desc_records;
    logic        frame_desc_protocol_error;
    logic        frame_desc_committed;

    logic        read_desc_valid;
    logic        read_desc_ready;
    logic        read_desc_slot_id;
    logic [27:0] read_desc_start_addr;
    logic [31:0] read_desc_records;
    logic        slot_fault_pulse;

    logic        gate_desc_valid;
    logic        gate_desc_ready;
    logic        scheduler_desc_valid;
    logic        scheduler_desc_ready;
    logic        scheduler_response_ready;
    logic        scheduler_frame_end;
    logic        scheduler_protocol_error;
    logic        scheduler_done_pulse;
    logic        scheduler_done_slot_id;
    logic        scheduler_fault_pulse;

    logic        gated_valid;
    logic        gated_ready;
    logic [31:0] gated_data;
    logic [3:0]  gated_keep;
    logic        gated_last;
    logic        gated_frame_end;
    logic        gated_protocol_error;

    rgb565_axis4_frame_commit u_frame_commit (
        .rst_n(rst_n), .clk(clk), .in_valid(commit_valid),
        .in_ready(commit_ready), .in_addr(commit_addr),
        .in_slot_id(commit_slot_id), .in_keep(commit_keep),
        .in_frame_end(commit_frame_end),
        .in_protocol_error(commit_protocol_error),
        .desc_valid(frame_desc_valid), .desc_ready(frame_desc_ready),
        .desc_start_addr(frame_desc_start_addr),
        .desc_slot_id(frame_desc_slot_id), .desc_bytes(frame_desc_bytes),
        .desc_records(frame_desc_records),
        .desc_protocol_error(frame_desc_protocol_error),
        .desc_committed(frame_desc_committed)
    );

    rgb565_axis4_frame_slot_table #(
        .SLOT0_BASE_ADDR(SLOT0_BASE_ADDR),
        .SLOT1_BASE_ADDR(SLOT1_BASE_ADDR),
        .SLOT_RECORD_CAPACITY(SLOT_RECORD_CAPACITY)
    ) u_frame_slot_table (
        .rst_n(rst_n), .clk(clk),
        .write_alloc_valid(write_alloc_valid),
        .write_alloc_ready(write_alloc_ready),
        .write_alloc_slot_id(write_alloc_slot_id),
        .write_alloc_base_addr(write_alloc_base_addr),
        .write_alloc_record_capacity(write_alloc_record_capacity),
        .commit_valid(frame_desc_valid), .commit_ready(frame_desc_ready),
        .commit_slot_id(frame_desc_slot_id),
        .commit_start_addr(frame_desc_start_addr),
        .commit_bytes(frame_desc_bytes),
        .commit_records(frame_desc_records),
        .commit_protocol_error(frame_desc_protocol_error),
        .commit_committed(frame_desc_committed),
        .read_desc_valid(read_desc_valid), .read_desc_ready(read_desc_ready),
        .read_desc_slot_id(read_desc_slot_id),
        .read_desc_start_addr(read_desc_start_addr), .read_desc_bytes(),
        .read_desc_records(read_desc_records),
        .read_desc_protocol_error(),
        .read_done_pulse(scheduler_done_pulse),
        .read_done_slot_id(scheduler_done_slot_id),
        .drop_frame_pulse(drop_frame_pulse), .drop_slot_id(drop_slot_id),
        .fault_pulse(slot_fault_pulse)
    );

    // Intent: Fork one queued descriptor atomically to the gate and scheduler.
    // Invariant: The slot enters READING only when both consumers accept it.
    // Assumption: Consumer ready outputs depend only on registered state, so this
    //             cross-gating creates no combinational ready loop.
    always_comb begin
        read_desc_ready = gate_desc_ready && scheduler_desc_ready;
        gate_desc_valid = read_desc_valid && scheduler_desc_ready;
        scheduler_desc_valid = read_desc_valid && gate_desc_ready;
        frame_done_pulse = scheduler_done_pulse;
        frame_done_slot_id = scheduler_done_slot_id;
        frame_fault_pulse = slot_fault_pulse || scheduler_fault_pulse;
    end

    rgb565_axis4_frame_read_scheduler #(
        .ADDR_STEP(TOKEN_ADDR_STEP)
    ) u_frame_read_scheduler (
        .rst_n(rst_n), .clk(clk), .desc_valid(scheduler_desc_valid),
        .desc_ready(scheduler_desc_ready), .desc_slot_id(read_desc_slot_id),
        .desc_start_addr(read_desc_start_addr),
        .desc_records(read_desc_records), .desc_committed(1'b1),
        .read_cmd_valid(read_cmd_valid), .read_cmd_ready(read_cmd_ready),
        .read_cmd_addr(read_cmd_addr),
        .read_response_accepted(read_valid && read_ready),
        .read_response_frame_end(read_frame_end),
        .read_response_ready(scheduler_response_ready),
        .read_response_frame_end_normalized(scheduler_frame_end),
        .read_response_protocol_error(scheduler_protocol_error),
        .frame_done_pulse(scheduler_done_pulse),
        .frame_done_slot_id(scheduler_done_slot_id),
        .frame_fault_pulse(scheduler_fault_pulse), .active()
    );

    rgb565_axis4_frame_readout_gate u_frame_readout_gate (
        .rst_n(rst_n), .clk(clk), .desc_valid(gate_desc_valid),
        .desc_ready(gate_desc_ready), .desc_committed(1'b1),
        .read_accept_enable(scheduler_response_ready),
        .frame_done_pulse(scheduler_done_pulse),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_keep(read_keep), .read_last(read_last),
        .read_frame_end(scheduler_frame_end),
        .read_protocol_error(read_protocol_error || scheduler_protocol_error),
        .out_valid(gated_valid), .out_ready(gated_ready),
        .out_data(gated_data), .out_keep(gated_keep),
        .out_last(gated_last), .out_frame_end(gated_frame_end),
        .out_protocol_error(gated_protocol_error), .drop_frame_pulse()
    );

    rgb565_axis4_pcie_mwr_path #(
        .BASE_ADDR(BASE_ADDR)
    ) u_pcie_mwr_path (
        .rst_n(rst_n), .clk(clk), .in_valid(gated_valid),
        .in_ready(gated_ready), .in_data(gated_data), .in_keep(gated_keep),
        .in_last(gated_last), .in_frame_end(gated_frame_end),
        .in_protocol_error(gated_protocol_error), .mwr32_req(mwr32_req),
        .mwr32_req_ack(mwr32_req_ack), .req_length(req_length),
        .req_addr(req_addr), .req_data(req_data), .req_keep(req_keep),
        .cross_4kb_boundary(cross_4kb_boundary), .req_last(req_last),
        .req_frame_end(req_frame_end),
        .req_protocol_error(req_protocol_error), .busy(busy)
    );
endmodule

`default_nettype wire
