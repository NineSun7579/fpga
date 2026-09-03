`default_nettype none

/**
 * @file rgb565_axis4_committed_pcie_mwr_path.sv
 * @brief 串接 DDR3 帧提交决策、帧读出门控和规范化 PCIe MWR 路径。
 *
 * @details
 * 写入侧的规范化 DDR3 记录先形成帧提交或作废描述符；已提交帧的首记录
 * opaque 地址和记录数驱动单 outstanding 读调度，返回记录随后进入 PCIe
 * MWR 路径，作废帧只产生回收提示。读调度器统一限定响应接收和完成条件，
 * 并把记录数/帧尾不一致归一化为协议错误。模块不保存帧数据、不解释
 * DDR3 地址单位，也不实例化厂商 DDR3/PCIe IP。
 *
 * @par Interface contract
 * - `commit_*` 输入按帧顺序描述已经写入 DDR3 记录模型的记录和 opaque 地址。
 * - 无协议错误的帧打开一次 `read_*` 读出窗口，并按记录数产生 `read_cmd_*`。
 * - 每条读命令握手后，外部必须返回一条保持到 `read_valid && read_ready` 的记录。
 * - 命令和零延迟响应可同周期握手；无当前命令时 `read_ready` 保持为零。
 * - `read_frame_end` 与描述符记录数不一致时结束当前帧并置请求协议错误。
 * - 带协议错误的帧不打开读出窗口，并输出一个 `drop_frame_pulse`。
 * - 正常、恢复性错误或零记录 fault 均输出 `frame_done_pulse`；后两者同时输出
 *   `frame_fault_pulse`。
 * - 已允许的读回记录由现有规范化 MWR path 转换为保持型请求。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，低有效异步断言；集成层必须相对 `clk` 同步释放。
 *
 * @par Assumptions
 * - commit 记录和后续 read 记录属于同一有序帧队列，映射由外部帧管理器保证。
 * - 外部读出器收到 `drop_frame_pulse` 后回收对应帧存储，不提供该帧读记录。
 *
 * @warning
 * 这是 vendor-independent 的帧完整性和请求连接切片，不证明 DDR3 持久化、
 * 真实 PCIe TLP/DMA、链路训练或主机内存写入。
 */
module rgb565_axis4_committed_pcie_mwr_path #(
    parameter logic [63:0] BASE_ADDR = 64'd0,
    parameter logic [27:0] TOKEN_ADDR_STEP = 28'd1
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        commit_valid,
    output logic             commit_ready,
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
    output logic             frame_done_pulse,
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
    logic        gate_desc_valid;
    logic        gate_desc_ready;
    logic        scheduler_desc_valid;
    logic        scheduler_desc_ready;
    logic        scheduler_response_ready;
    logic        scheduler_frame_end;
    logic        scheduler_protocol_error;
    logic [27:0] frame_desc_start_addr;
    logic [31:0] frame_desc_records;
    logic        frame_desc_committed;
    logic        gated_valid;
    logic        gated_ready;
    logic [31:0] gated_data;
    logic [3:0]  gated_keep;
    logic        gated_last;
    logic        gated_frame_end;
    logic        gated_protocol_error;

    rgb565_axis4_frame_commit u_frame_commit (
        .rst_n(rst_n), .clk(clk), .in_valid(commit_valid), .in_ready(commit_ready),
        .in_addr(commit_addr), .in_keep(commit_keep), .in_frame_end(commit_frame_end),
        .in_protocol_error(commit_protocol_error), .desc_valid(frame_desc_valid),
        .desc_ready(frame_desc_ready), .desc_start_addr(frame_desc_start_addr),
        .desc_bytes(), .desc_records(frame_desc_records),
        .desc_protocol_error(),
        .desc_committed(frame_desc_committed)
    );

    // Intent: Fork one descriptor atomically to the gate and scheduler.
    // Invariant: A descriptor handshake occurs only when both consumers accept it.
    // Assumption: Both consumer ready outputs depend only on registered state, not
    //             on their valid inputs, so this cross-gating creates no ready loop.
    always_comb begin
        frame_desc_ready = gate_desc_ready && scheduler_desc_ready;
        gate_desc_valid = frame_desc_valid && scheduler_desc_ready;
        scheduler_desc_valid = frame_desc_valid && gate_desc_ready;
    end

    rgb565_axis4_frame_read_scheduler #(
        .ADDR_STEP(TOKEN_ADDR_STEP)
    ) u_frame_read_scheduler (
        .rst_n(rst_n), .clk(clk), .desc_valid(scheduler_desc_valid),
        .desc_ready(scheduler_desc_ready), .desc_start_addr(frame_desc_start_addr),
        .desc_records(frame_desc_records), .desc_committed(frame_desc_committed),
        .read_cmd_valid(read_cmd_valid), .read_cmd_ready(read_cmd_ready),
        .read_cmd_addr(read_cmd_addr),
        .read_response_accepted(read_valid && read_ready),
        .read_response_frame_end(read_frame_end),
        .read_response_ready(scheduler_response_ready),
        .read_response_frame_end_normalized(scheduler_frame_end),
        .read_response_protocol_error(scheduler_protocol_error),
        .frame_done_pulse(frame_done_pulse),
        .frame_fault_pulse(frame_fault_pulse), .active()
    );

    rgb565_axis4_frame_readout_gate u_frame_readout_gate (
        .rst_n(rst_n), .clk(clk), .desc_valid(gate_desc_valid),
        .desc_ready(gate_desc_ready), .desc_committed(frame_desc_committed),
        .read_accept_enable(scheduler_response_ready),
        .frame_done_pulse(frame_done_pulse),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_keep(read_keep), .read_last(read_last),
        .read_frame_end(scheduler_frame_end),
        .read_protocol_error(read_protocol_error || scheduler_protocol_error),
        .out_valid(gated_valid),
        .out_ready(gated_ready), .out_data(gated_data), .out_keep(gated_keep),
        .out_last(gated_last), .out_frame_end(gated_frame_end),
        .out_protocol_error(gated_protocol_error),
        .drop_frame_pulse(drop_frame_pulse)
    );

    rgb565_axis4_pcie_mwr_path #(.BASE_ADDR(BASE_ADDR)) u_pcie_mwr_path (
        .rst_n(rst_n), .clk(clk), .in_valid(gated_valid), .in_ready(gated_ready),
        .in_data(gated_data), .in_keep(gated_keep), .in_last(gated_last),
        .in_frame_end(gated_frame_end),
        .in_protocol_error(gated_protocol_error), .mwr32_req(mwr32_req),
        .mwr32_req_ack(mwr32_req_ack), .req_length(req_length),
        .req_addr(req_addr), .req_data(req_data), .req_keep(req_keep),
        .cross_4kb_boundary(cross_4kb_boundary), .req_last(req_last),
        .req_frame_end(req_frame_end),
        .req_protocol_error(req_protocol_error), .busy(busy)
    );

endmodule

`default_nettype wire
