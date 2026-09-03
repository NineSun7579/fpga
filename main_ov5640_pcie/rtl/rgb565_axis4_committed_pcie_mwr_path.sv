`default_nettype none

/**
 * @file rgb565_axis4_committed_pcie_mwr_path.sv
 * @brief 串接 DDR3 帧提交决策、帧读出门控和规范化 PCIe MWR 路径。
 *
 * @details
 * 写入侧的规范化 DDR3 记录先形成帧提交或作废描述符；已提交帧随后允许
 * 对应的 DDR3 读回记录进入 PCIe MWR 路径，作废帧只产生回收提示。模块
 * 不保存帧数据、不生成 DDR3 读地址，也不实例化厂商 DDR3/PCIe IP。
 *
 * @par Interface contract
 * - `commit_*` 输入按帧顺序描述已经写入 DDR3 记录模型的记录边界。
 * - 无协议错误的帧打开一次 `read_*` 读出窗口，直到帧尾记录完成握手。
 * - 带协议错误的帧不打开读出窗口，并输出一个 `drop_frame_pulse`。
 * - 已允许的读回记录由现有规范化 MWR path 转换为保持型请求。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，异步断言；释放行为属于集成层责任。
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
    parameter logic [63:0] BASE_ADDR = 64'd0
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        commit_valid,
    output logic             commit_ready,
    input  wire logic [3:0]  commit_keep,
    input  wire logic        commit_frame_end,
    input  wire logic        commit_protocol_error,
    input  wire logic        read_valid,
    output logic             read_ready,
    input  wire logic [31:0] read_data,
    input  wire logic [3:0]  read_keep,
    input  wire logic        read_last,
    input  wire logic        read_frame_end,
    input  wire logic        read_protocol_error,
    output logic             drop_frame_pulse,
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
        .in_keep(commit_keep), .in_frame_end(commit_frame_end),
        .in_protocol_error(commit_protocol_error), .desc_valid(frame_desc_valid),
        .desc_ready(frame_desc_ready), .desc_bytes(), .desc_records(),
        .desc_protocol_error(),
        .desc_committed(frame_desc_committed)
    );

    rgb565_axis4_frame_readout_gate u_frame_readout_gate (
        .rst_n(rst_n), .clk(clk), .desc_valid(frame_desc_valid),
        .desc_ready(frame_desc_ready), .desc_committed(frame_desc_committed),
        .read_valid(read_valid), .read_ready(read_ready), .read_data(read_data),
        .read_keep(read_keep), .read_last(read_last), .read_frame_end(read_frame_end),
        .read_protocol_error(read_protocol_error), .out_valid(gated_valid),
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
