`default_nettype none

/**
 * @file rgb565_axis4_cdc_bridge.sv
 * @brief 为 staging beat 提供命名明确的双时钟 CDC 边界。
 *
 * @details
 * 本封装将 `rgb565_axis4_async_fifo` 暴露为上游/下游 staging 接口，便于
 * 后续分别连接 `cam_pclk`、DDR3 用户时钟或 PCIe 用户时钟。事件标志与
 * 数据一起排队，避免帧尾、行尾和协议错误脱离对应 beat。
 *
 * @warning
 * 上游必须遵守 `in_valid && in_ready`；如果当前采集源没有输入背压，不能
 * 仅靠本模块证明持续满 FIFO 时不会丢帧。FIFO 深度、复位释放、RAM 推断、
 * CDC/RDC 工具分类和目标时钟约束仍由最终集成审核负责。
 */
module rgb565_axis4_cdc_bridge #(
    parameter integer ADDR_WIDTH = 4
) (
    input  wire logic       in_rst_n,
    input  wire logic       in_clk,
    input  wire logic       in_valid,
    output logic            in_ready,
    input  wire logic [31:0] in_data,
    input  wire logic [3:0]  in_keep,
    input  wire logic         in_last,
    input  wire logic [4:0]   in_user,
    input  wire logic         out_rst_n,
    input  wire logic         out_clk,
    output logic              out_valid,
    input  wire logic          out_ready,
    output logic [31:0]      out_data,
    output logic [3:0]       out_keep,
    output logic              out_last,
    output logic [4:0]       out_user
);
    rgb565_axis4_async_fifo #(.ADDR_WIDTH(ADDR_WIDTH)) u_staging_fifo (
        .wr_rst_n (in_rst_n), .wr_clk (in_clk), .wr_valid (in_valid), .wr_ready (in_ready),
        .wr_data  (in_data), .wr_keep  (in_keep), .wr_last  (in_last), .wr_user  (in_user),
        .rd_rst_n (out_rst_n), .rd_clk (out_clk), .rd_valid (out_valid), .rd_ready(out_ready),
        .rd_data  (out_data), .rd_keep  (out_keep), .rd_last  (out_last), .rd_user  (out_user)
    );
endmodule

`default_nettype wire
