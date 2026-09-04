`default_nettype none

/**
 * @file rgb565_pg2l50h_pcie_tx_top_adapter.sv
 * @brief Connect the camera CDC arbiter to the complete PCIe TX top.
 *
 * @details
 * This project-owned adapter is the boundary between the camera/native
 * request arbiter and the unchanged Pango `ips2l_pcie_dma_tx_top`. It exposes
 * the three AXIS TX channels and BAR read ports to the surrounding product
 * wrapper while keeping all four request types as one atomic bundle.
 *
 * @par Interface contract
 * - Camera requests originate in `camera_clk` and are full-DWORD MWR32
 *   transactions. The camera bundle must remain stable until its ACK.
 * - Native requests and all vendor TX ports are synchronous to `pcie_clk`.
 * - The adapter does not translate partial byte enables or define host DMA
 *   ownership. Those contracts remain outside this boundary.
 *
 * @par Clock and reset
 * - Camera domain: `camera_clk`/`camera_rst_n`, normally DDR3 `core_clk`.
 * - PCIe domain: `pcie_clk`/`pcie_rst_n`, normally the PCIe user clock.
 * - Both resets are asynchronously asserted and must be synchronously
 *   released in their respective domains by the board integration.
 *
 * @warning
 * This module proves only project-to-vendor TX-top connectivity. It does not
 * prove PCIe link training, TLP delivery, host memory writes, or placed-design
 * CDC/RDC and bundled-data timing constraints.
 */
module rgb565_pg2l50h_pcie_tx_top_adapter #(
    parameter logic [2:0] DEVICE_TYPE = 3'd0,
    parameter integer     ADDR_WIDTH  = 12
) (
    input  wire logic        camera_rst_n,
    input  wire logic        camera_clk,
    input  wire logic        camera_mwr32_req,
    output logic             camera_mwr32_req_ack,
    input  wire logic [9:0]  camera_req_length,
    input  wire logic [63:0] camera_req_addr,
    input  wire logic [31:0] camera_req_data,
    output logic             camera_channel_ready,
    output logic             camera_cdc_fault_pulse,
    output logic             camera_cdc_fault_sticky,

    input  wire logic        pcie_rst_n,
    input  wire logic        pcie_clk,
    input  wire logic        native_user_define_data_flag,
    input  wire logic        native_mwr32_req,
    output logic             native_mwr32_req_ack,
    input  wire logic        native_mwr64_req,
    output logic             native_mwr64_req_ack,
    input  wire logic        native_mrd32_req,
    output logic             native_mrd32_req_ack,
    input  wire logic        native_mrd64_req,
    output logic             native_mrd64_req_ack,
    input  wire logic [9:0]  native_req_length,
    input  wire logic [63:0] native_req_addr,
    input  wire logic [31:0] native_req_data,
    output logic             pcie_channel_ready,
    output logic             pcie_cdc_fault_pulse,
    output logic             pcie_cdc_fault_sticky,

    input  wire logic [7:0]  cfg_pbus_num,
    input  wire logic [4:0]  cfg_pbus_dev_num,
    input  wire logic [2:0]  cfg_max_rd_req_size,
    input  wire logic [2:0]  cfg_max_payload_size,
    input  wire logic        axis_slave0_trdy,
    output wire             axis_slave0_tvld,
    output wire [127:0]     axis_slave0_tdata,
    output wire             axis_slave0_tlast,
    output wire             axis_slave0_tuser,
    input  wire logic        axis_slave1_trdy,
    output wire             axis_slave1_tvld,
    output wire [127:0]     axis_slave1_tdata,
    output wire             axis_slave1_tlast,
    output wire             axis_slave1_tuser,
    input  wire logic        axis_slave2_trdy,
    output wire             axis_slave2_tvld,
    output wire [127:0]     axis_slave2_tdata,
    output wire             axis_slave2_tlast,
    output wire             axis_slave2_tuser,
    output wire             bar0_rd_clk_en,
    output wire [ADDR_WIDTH-1:0] bar0_rd_addr,
    input  wire logic [127:0] bar0_rd_data,
    output wire             bar2_rd_clk_en,
    output wire [ADDR_WIDTH-1:0] bar2_rd_addr,
    input  wire logic [127:0] bar2_rd_data,
    input  wire logic [2:0]  mrd_tc,
    input  wire logic [2:0]  mrd_attr,
    input  wire logic [9:0]  mrd_length,
    input  wire logic [15:0] mrd_id,
    input  wire logic [7:0]  mrd_tag,
    input  wire logic [63:0] mrd_addr,
    input  wire logic        cpld_req_vld,
    output wire             cpld_req_rdy,
    output wire             cpld_tx_rdy,
    input  wire logic        cpld_rcv,
    input  wire logic [7:0]  cpld_tag,
    output wire             tag_full,
    input  wire logic        tx_restart
);
    logic        tx_user_define_data_flag;
    logic        tx_mwr32_req;
    logic        tx_mwr32_req_ack;
    logic        tx_mwr64_req;
    logic        tx_mwr64_req_ack;
    logic        tx_mrd32_req;
    logic        tx_mrd32_req_ack;
    logic        tx_mrd64_req;
    logic        tx_mrd64_req_ack;
    logic [9:0]  tx_req_length;
    logic [63:0] tx_req_addr;
    logic [31:0] tx_req_data;

    rgb565_pg2l50h_pcie_tx_cdc_arbiter u_request_boundary (
        .camera_rst_n                  (camera_rst_n),
        .camera_clk                    (camera_clk),
        .camera_mwr32_req              (camera_mwr32_req),
        .camera_mwr32_req_ack          (camera_mwr32_req_ack),
        .camera_req_length             (camera_req_length),
        .camera_req_addr               (camera_req_addr),
        .camera_req_data               (camera_req_data),
        .camera_channel_ready          (camera_channel_ready),
        .camera_cdc_fault_pulse        (camera_cdc_fault_pulse),
        .camera_cdc_fault_sticky       (camera_cdc_fault_sticky),
        .pcie_rst_n                    (pcie_rst_n),
        .pcie_clk                      (pcie_clk),
        .native_user_define_data_flag  (native_user_define_data_flag),
        .native_mwr32_req              (native_mwr32_req),
        .native_mwr32_req_ack          (native_mwr32_req_ack),
        .native_mwr64_req              (native_mwr64_req),
        .native_mwr64_req_ack          (native_mwr64_req_ack),
        .native_mrd32_req              (native_mrd32_req),
        .native_mrd32_req_ack          (native_mrd32_req_ack),
        .native_mrd64_req              (native_mrd64_req),
        .native_mrd64_req_ack          (native_mrd64_req_ack),
        .native_req_length             (native_req_length),
        .native_req_addr               (native_req_addr),
        .native_req_data               (native_req_data),
        .pcie_channel_ready            (pcie_channel_ready),
        .pcie_cdc_fault_pulse          (pcie_cdc_fault_pulse),
        .pcie_cdc_fault_sticky         (pcie_cdc_fault_sticky),
        .tx_user_define_data_flag      (tx_user_define_data_flag),
        .tx_mwr32_req                  (tx_mwr32_req),
        .tx_mwr32_req_ack              (tx_mwr32_req_ack),
        .tx_mwr64_req                  (tx_mwr64_req),
        .tx_mwr64_req_ack              (tx_mwr64_req_ack),
        .tx_mrd32_req                  (tx_mrd32_req),
        .tx_mrd32_req_ack              (tx_mrd32_req_ack),
        .tx_mrd64_req                  (tx_mrd64_req),
        .tx_mrd64_req_ack              (tx_mrd64_req_ack),
        .tx_req_length                 (tx_req_length),
        .tx_req_addr                   (tx_req_addr),
        .tx_req_data                   (tx_req_data)
    );

    ips2l_pcie_dma_tx_top #(
        .DEVICE_TYPE                   (DEVICE_TYPE),
        .ADDR_WIDTH                    (ADDR_WIDTH)
    ) u_vendor_tx_top (
        .clk                            (pcie_clk),
        .rst_n                          (pcie_rst_n),
        .i_cfg_pbus_num                 (cfg_pbus_num),
        .i_cfg_pbus_dev_num             (cfg_pbus_dev_num),
        .i_cfg_max_rd_req_size          (cfg_max_rd_req_size),
        .i_cfg_max_payload_size         (cfg_max_payload_size),
        .i_axis_slave0_trdy             (axis_slave0_trdy),
        .o_axis_slave0_tvld             (axis_slave0_tvld),
        .o_axis_slave0_tdata            (axis_slave0_tdata),
        .o_axis_slave0_tlast            (axis_slave0_tlast),
        .o_axis_slave0_tuser            (axis_slave0_tuser),
        .i_axis_slave1_trdy             (axis_slave1_trdy),
        .o_axis_slave1_tvld             (axis_slave1_tvld),
        .o_axis_slave1_tdata            (axis_slave1_tdata),
        .o_axis_slave1_tlast             (axis_slave1_tlast),
        .o_axis_slave1_tuser             (axis_slave1_tuser),
        .i_axis_slave2_trdy             (axis_slave2_trdy),
        .o_axis_slave2_tvld             (axis_slave2_tvld),
        .o_axis_slave2_tdata            (axis_slave2_tdata),
        .o_axis_slave2_tlast            (axis_slave2_tlast),
        .o_axis_slave2_tuser            (axis_slave2_tuser),
        .i_user_define_data_flag        (tx_user_define_data_flag),
        .i_mwr32_req                    (tx_mwr32_req),
        .o_mwr32_req_ack                (tx_mwr32_req_ack),
        .i_mwr64_req                    (tx_mwr64_req),
        .o_mwr64_req_ack                (tx_mwr64_req_ack),
        .i_mrd32_req                    (tx_mrd32_req),
        .o_mrd32_req_ack                (tx_mrd32_req_ack),
        .i_mrd64_req                    (tx_mrd64_req),
        .o_mrd64_req_ack                (tx_mrd64_req_ack),
        .i_req_length                   (tx_req_length),
        .i_req_addr                     (tx_req_addr),
        .i_req_data                     (tx_req_data),
        .o_bar0_rd_clk_en               (bar0_rd_clk_en),
        .o_bar0_rd_addr                 (bar0_rd_addr),
        .i_bar0_rd_data                 (bar0_rd_data),
        .o_bar2_rd_clk_en               (bar2_rd_clk_en),
        .o_bar2_rd_addr                 (bar2_rd_addr),
        .i_bar2_rd_data                 (bar2_rd_data),
        .i_mrd_tc                       (mrd_tc),
        .i_mrd_attr                     (mrd_attr),
        .i_mrd_length                   (mrd_length),
        .i_mrd_id                       (mrd_id),
        .i_mrd_tag                      (mrd_tag),
        .i_mrd_addr                     (mrd_addr),
        .i_cpld_req_vld                 (cpld_req_vld),
        .o_cpld_req_rdy                 (cpld_req_rdy),
        .o_cpld_tx_rdy                  (cpld_tx_rdy),
        .i_cpld_rcv                     (cpld_rcv),
        .i_cpld_tag                     (cpld_tag),
        .o_tag_full                     (tag_full),
        .i_tx_restart                   (tx_restart)
    );
endmodule

`default_nettype wire
