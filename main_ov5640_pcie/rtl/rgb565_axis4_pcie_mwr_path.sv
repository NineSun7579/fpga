`default_nettype none

/**
 * @file rgb565_axis4_pcie_mwr_path.sv
 * @brief 串接 staging、规范化 MWR 描述符和 PCIe 请求桥。
 *
 * @details
 * 本模块只形成 vendor-independent 的请求路径：每个 staging beat 先被
 * 转换为带地址/长度/边界信息的请求，再映射到活动 PCIe 控制器的
 * `mwr32_req`/ack 接口。请求期间数据和事件元数据保持稳定。
 *
 * @warning
 * 该路径不实例化厂商 PCIe IP，也不编码 TLP；`req_keep` 仍是旁路信息，
 * 不能据此推断真实 byte enable、DMA、链路或主机内存写入已经通过。
 */
module rgb565_axis4_pcie_mwr_path #(
    parameter logic [63:0] BASE_ADDR = 64'd0
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        in_valid,
    output logic             in_ready,
    input  wire logic [31:0] in_data,
    input  wire logic [3:0]  in_keep,
    input  wire logic        in_last,
    input  wire logic        in_frame_end,
    input  wire logic        in_protocol_error,
    output logic             mwr32_req,
    input  wire logic         mwr32_req_ack,
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
    logic descriptor_valid;
    logic descriptor_ready;
    logic [63:0] descriptor_addr;
    logic [9:0] descriptor_length;
    logic [31:0] descriptor_data;
    logic [3:0] descriptor_keep;
    logic descriptor_last, descriptor_frame_end, descriptor_protocol_error;
    logic descriptor_boundary;

    rgb565_axis4_mwr_descriptor #(.BASE_ADDR(BASE_ADDR)) u_descriptor (
        .rst_n(rst_n), .clk(clk), .in_valid(in_valid), .in_ready(in_ready),
        .in_data(in_data), .in_keep(in_keep), .in_last(in_last),
        .in_frame_end(in_frame_end), .in_protocol_error(in_protocol_error),
        .req_valid(descriptor_valid), .req_ready(descriptor_ready),
        .req_addr(descriptor_addr), .req_length_dw_minus1(descriptor_length),
        .req_data(descriptor_data), .req_keep(descriptor_keep), .req_last(descriptor_last),
        .req_frame_end(descriptor_frame_end), .req_protocol_error(descriptor_protocol_error),
        .req_cross_4kb_boundary(descriptor_boundary)
    );

    rgb565_axis4_pcie_mwr_bridge u_bridge (
        .rst_n(rst_n), .clk(clk), .in_valid(descriptor_valid), .in_ready(descriptor_ready),
        .in_addr(descriptor_addr), .in_length_dw_minus1(descriptor_length),
        .in_data(descriptor_data), .in_keep(descriptor_keep),
        .in_cross_4kb_boundary(descriptor_boundary), .mwr32_req(mwr32_req),
        .mwr32_req_ack(mwr32_req_ack), .req_length(req_length), .req_addr(req_addr),
        .req_data(req_data), .req_keep(req_keep), .cross_4kb_boundary(cross_4kb_boundary),
        .busy(busy)
    );

    assign req_last = descriptor_last;
    assign req_frame_end = descriptor_frame_end;
    assign req_protocol_error = descriptor_protocol_error;
endmodule

`default_nettype wire
