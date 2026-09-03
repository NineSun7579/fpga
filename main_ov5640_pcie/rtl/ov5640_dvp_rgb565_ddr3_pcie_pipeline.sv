`default_nettype none

/**
 * @file ov5640_dvp_rgb565_ddr3_pcie_pipeline.sv
 * @brief 连接 OV5640 DVP、双槽 DDR3 记录边界和 PCIe MWR 请求边界。
 *
 * @details
 * 模块把 DVP 捕获、灰度/打包、异步 staging、按槽 DDR3 writer 和 committed
 * PCIe 路径连接为一个可综合的 vendor-independent 顶层。每条 writer 记录先在
 * `ddr_write_valid && ddr_write_ready` 边沿被外部 DDR3 适配层接受，下一阶段才
 * 交给 frame commit；因此已提交描述符不会先于对应写记录持久化边界。
 *
 * @par Interface contract
 * - camera 侧使用 `in_rst_n/cam_pclk`，DDR3/PCIe 记录侧使用 `io_rst_n/io_clk`。
 * - DDR3 写记录先完成外部握手，再完成内部 commit 握手；等待 commit 时不会
 *   重复拉高 `ddr_write_valid`，writer 字段保持稳定。
 * - DDR3 读命令和响应使用单 outstanding、保持型 ready/valid 合同。
 * - 错误帧输出带槽 drop，正常或读协议 fault 输出带槽 done。
 * - PCIe 输出仍是规范化 MWR 请求，不是厂商 TLP 或 DMA 应用口。
 *
 * @par Clock and reset
 * - Camera clock: `cam_pclk`；reset: `in_rst_n`，低有效异步断言。
 * - IO clock: `io_clk`；reset: `io_rst_n`，低有效异步断言。
 * - 两个复位均必须在各自时钟域同步释放；跨域 staging 使用独立 FIFO 边界。
 *
 * @par Assumptions
 * - `ddr_write_ready` 只表示当前规范化写记录已被外部 DDR3 适配层接受。
 * - 外部 DDR3 读模型按命令返回对应 token，且不丢失、不重复、不乱序。
 * - 槽基、容量与 `TOKEN_ADDR_STEP` 定义的两个 token 区域不重叠。
 *
 * @warning
 * 本模块不实例化 PG2L50H DDR3/PCIe IP，不证明真实地址单位、初始化/校准、
 * TLP/byte-enable、链路训练、RK3568 DMA、主机内存或板级时序。
 */
module ov5640_dvp_rgb565_ddr3_pcie_pipeline #(
    parameter integer      FIFO_ADDR_WIDTH = 3,
    parameter logic [27:0] TOKEN_ADDR_STEP = 28'd1,
    parameter logic [27:0] SLOT0_BASE_ADDR = 28'd0,
    parameter logic [27:0] SLOT1_BASE_ADDR = 28'd1024,
    parameter logic [31:0] SLOT_RECORD_CAPACITY = 32'd1024,
    parameter logic [63:0] PCIE_BASE_ADDR = 64'd0
) (
    input  wire logic         in_rst_n,
    input  wire logic         cam_pclk,
    input  wire logic         cam_vsync,
    input  wire logic         cam_href,
    input  wire logic [7:0]   cam_data,
    input  wire logic         io_rst_n,
    input  wire logic         io_clk,
    output logic              source_overflow,
    output logic              ddr_write_valid,
    input  wire logic         ddr_write_ready,
    output logic              ddr_write_slot_id,
    output logic [27:0]       ddr_write_addr,
    output logic [3:0]        ddr_write_awlen,
    output logic [127:0]      ddr_write_data,
    output logic [15:0]       ddr_write_strb,
    output logic              ddr_write_last,
    output logic              ddr_write_frame_end,
    output logic              ddr_write_protocol_error,
    output logic              ddr_read_cmd_valid,
    input  wire logic         ddr_read_cmd_ready,
    output logic [27:0]       ddr_read_cmd_addr,
    input  wire logic         ddr_read_valid,
    output logic              ddr_read_ready,
    input  wire logic [31:0]  ddr_read_data,
    input  wire logic [3:0]   ddr_read_keep,
    input  wire logic         ddr_read_last,
    input  wire logic         ddr_read_frame_end,
    input  wire logic         ddr_read_protocol_error,
    output logic              drop_frame_pulse,
    output logic              drop_slot_id,
    output logic              frame_done_pulse,
    output logic              frame_done_slot_id,
    output logic              frame_fault_pulse,
    output logic              mwr32_req,
    input  wire logic         mwr32_req_ack,
    output logic [9:0]        req_length,
    output logic [63:0]       req_addr,
    output logic [31:0]       req_data,
    output logic [3:0]        req_keep,
    output logic              cross_4kb_boundary,
    output logic              req_last,
    output logic              req_frame_end,
    output logic              req_protocol_error,
    output logic              pcie_busy
);
    logic        staging_valid;
    logic        staging_ready;
    logic [31:0] staging_data;
    logic [3:0]  staging_keep;
    logic        staging_last;
    logic [4:0]  staging_user;

    logic        write_alloc_valid;
    logic        write_alloc_ready;
    logic        write_alloc_slot_id;
    logic [27:0] write_alloc_base_addr;
    logic [31:0] write_alloc_record_capacity;

    logic        writer_valid;
    logic        writer_ready;
    logic        commit_valid;
    logic        commit_ready;
    logic        ddr_accepted_reg;

    ov5640_dvp_rgb565_cdc_staging_pipeline #(
        .FIFO_ADDR_WIDTH(FIFO_ADDR_WIDTH)
    ) u_capture (
        .in_rst_n(in_rst_n), .cam_pclk(cam_pclk), .cam_vsync(cam_vsync),
        .cam_href(cam_href), .cam_data(cam_data), .out_rst_n(io_rst_n),
        .out_clk(io_clk), .out_valid(staging_valid),
        .out_ready(staging_ready), .out_data(staging_data),
        .out_keep(staging_keep), .out_last(staging_last),
        .out_user(staging_user), .source_overflow(source_overflow)
    );

    rgb565_axis4_ddr3_write_descriptor #(
        .ADDR_STEP(TOKEN_ADDR_STEP)
    ) u_ddr_writer (
        .rst_n(io_rst_n), .clk(io_clk),
        .frame_alloc_valid(write_alloc_valid),
        .frame_alloc_ready(write_alloc_ready),
        .frame_alloc_slot_id(write_alloc_slot_id),
        .frame_alloc_base_addr(write_alloc_base_addr),
        .frame_alloc_record_capacity(write_alloc_record_capacity),
        .in_valid(staging_valid), .in_ready(staging_ready),
        .in_data(staging_data), .in_keep(staging_keep),
        .in_last(staging_last), .in_frame_end(staging_user[3]),
        .in_protocol_error(staging_user[4]), .write_valid(writer_valid),
        .write_ready(writer_ready), .write_slot_id(ddr_write_slot_id),
        .write_addr(ddr_write_addr), .write_awlen(ddr_write_awlen),
        .write_data(ddr_write_data), .write_strb(ddr_write_strb),
        .write_last(ddr_write_last), .write_frame_end(ddr_write_frame_end),
        .write_protocol_error(ddr_write_protocol_error)
    );

    // Intent: Serialize each record through DDR acceptance before frame accounting.
    // Invariant: A record is presented to DDR at most once and cannot reach commit
    //            until the prior DDR acceptance edge has completed.
    always_comb begin
        ddr_write_valid = writer_valid && !ddr_accepted_reg;
        commit_valid = writer_valid && ddr_accepted_reg;
        writer_ready = commit_valid && commit_ready;
    end

    always_ff @(posedge io_clk or negedge io_rst_n) begin
        if (!io_rst_n) begin
            ddr_accepted_reg <= 1'b0;
        end else if (!writer_valid || writer_ready) begin
            ddr_accepted_reg <= 1'b0;
        end else if (!ddr_accepted_reg && ddr_write_ready) begin
            ddr_accepted_reg <= 1'b1;
        end
    end

    rgb565_axis4_committed_pcie_mwr_path #(
        .BASE_ADDR(PCIE_BASE_ADDR), .TOKEN_ADDR_STEP(TOKEN_ADDR_STEP),
        .SLOT0_BASE_ADDR(SLOT0_BASE_ADDR),
        .SLOT1_BASE_ADDR(SLOT1_BASE_ADDR),
        .SLOT_RECORD_CAPACITY(SLOT_RECORD_CAPACITY)
    ) u_committed_path (
        .rst_n(io_rst_n), .clk(io_clk),
        .write_alloc_valid(write_alloc_valid),
        .write_alloc_ready(write_alloc_ready),
        .write_alloc_slot_id(write_alloc_slot_id),
        .write_alloc_base_addr(write_alloc_base_addr),
        .write_alloc_record_capacity(write_alloc_record_capacity),
        .commit_valid(commit_valid), .commit_ready(commit_ready),
        .commit_slot_id(ddr_write_slot_id), .commit_addr(ddr_write_addr),
        .commit_keep(ddr_write_strb[3:0]),
        .commit_frame_end(ddr_write_frame_end),
        .commit_protocol_error(ddr_write_protocol_error),
        .read_cmd_valid(ddr_read_cmd_valid),
        .read_cmd_ready(ddr_read_cmd_ready),
        .read_cmd_addr(ddr_read_cmd_addr), .read_valid(ddr_read_valid),
        .read_ready(ddr_read_ready), .read_data(ddr_read_data),
        .read_keep(ddr_read_keep), .read_last(ddr_read_last),
        .read_frame_end(ddr_read_frame_end),
        .read_protocol_error(ddr_read_protocol_error),
        .drop_frame_pulse(drop_frame_pulse), .drop_slot_id(drop_slot_id),
        .frame_done_pulse(frame_done_pulse),
        .frame_done_slot_id(frame_done_slot_id),
        .frame_fault_pulse(frame_fault_pulse), .mwr32_req(mwr32_req),
        .mwr32_req_ack(mwr32_req_ack), .req_length(req_length),
        .req_addr(req_addr), .req_data(req_data), .req_keep(req_keep),
        .cross_4kb_boundary(cross_4kb_boundary), .req_last(req_last),
        .req_frame_end(req_frame_end),
        .req_protocol_error(req_protocol_error), .busy(pcie_busy)
    );
endmodule

`default_nettype wire
