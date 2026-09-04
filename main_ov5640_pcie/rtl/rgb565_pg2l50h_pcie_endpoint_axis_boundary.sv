`default_nettype none

/**
 * @file rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv
 * @brief Bind the camera TX path to the generated PCIe Endpoint AXIS subset.
 *
 * @details
 * This project-owned module wraps the verified complete TX-top adapter and
 * names its PCIe-facing ports after the generated `pcie_test` Endpoint. The
 * Endpoint owns `pclk_div2`, `core_rst_n`, configuration identity/capability
 * outputs, and AXIS slave ready. The camera path owns AXIS slave
 * valid/data/last/user. Native DMA, MRD, CPLD, BAR-read, and restart sources
 * are intentionally inactive in this camera-only boundary.
 *
 * @par Interface contract
 * - `camera_*` is synchronous to `camera_clk` and reset by `camera_rst_n`.
 * - All TX and Endpoint AXIS signals are synchronous to
 *   `endpoint_pclk_div2` and reset by `endpoint_core_rst_n`.
 * - AXIS0 carries CPLD, AXIS1 carries MRD, and AXIS2 carries MWR traffic.
 * - Endpoint link status is observation only. Flow control is exclusively the
 *   corresponding AXIS ready/valid handshake; this module never fabricates an
 *   ACK, silently drops a request, or adds an unowned replay policy.
 * - In-flight reset recovery retains the mailbox fail-stop behavior documented
 *   by `rgb565_pg2l50h_pcie_tx_top_adapter`.
 *
 * @warning
 * This module does not instantiate `pcie_test`, the PCIe PHY, APB/DBI logic,
 * RX AXIS handling, or an RK3568 driver. A stub-based test proves only the
 * project-to-Endpoint port contract, not LTSSM or serial-link operation.
 */
module rgb565_pg2l50h_pcie_endpoint_axis_boundary #(
    parameter logic [2:0] DEVICE_TYPE = 3'd0,
    parameter integer     ADDR_WIDTH = 12
) (
    input  wire logic         camera_rst_n,
    input  wire logic         camera_clk,
    input  wire logic         camera_mwr32_req,
    output logic              camera_mwr32_req_ack,
    input  wire logic [9:0]   camera_req_length,
    input  wire logic [63:0]  camera_req_addr,
    input  wire logic [31:0]  camera_req_data,
    output logic              camera_channel_ready,
    output logic              camera_cdc_fault_pulse,
    output logic              camera_cdc_fault_sticky,

    input  wire logic         endpoint_pclk_div2,
    input  wire logic         endpoint_core_rst_n,
    input  wire logic         endpoint_smlh_link_up,
    input  wire logic         endpoint_rdlh_link_up,
    output logic              observed_smlh_link_up,
    output logic              observed_rdlh_link_up,
    output logic              pcie_channel_ready,
    output logic              pcie_cdc_fault_pulse,
    output logic              pcie_cdc_fault_sticky,

    input  wire logic [7:0]   cfg_pbus_num,
    input  wire logic [4:0]   cfg_pbus_dev_num,
    input  wire logic [2:0]   cfg_max_rd_req_size,
    input  wire logic [2:0]   cfg_max_payload_size,

    input  wire logic         endpoint_axis_slave0_tready,
    output wire               endpoint_axis_slave0_tvalid,
    output wire [127:0]       endpoint_axis_slave0_tdata,
    output wire               endpoint_axis_slave0_tlast,
    output wire               endpoint_axis_slave0_tuser,
    input  wire logic         endpoint_axis_slave1_tready,
    output wire               endpoint_axis_slave1_tvalid,
    output wire [127:0]       endpoint_axis_slave1_tdata,
    output wire               endpoint_axis_slave1_tlast,
    output wire               endpoint_axis_slave1_tuser,
    input  wire logic         endpoint_axis_slave2_tready,
    output wire               endpoint_axis_slave2_tvalid,
    output wire [127:0]       endpoint_axis_slave2_tdata,
    output wire               endpoint_axis_slave2_tlast,
    output wire               endpoint_axis_slave2_tuser
);
    // Intent: Preserve Endpoint link state as telemetry without adding policy.
    always_comb begin
        observed_smlh_link_up = endpoint_smlh_link_up;
        observed_rdlh_link_up = endpoint_rdlh_link_up;
    end

    rgb565_pg2l50h_pcie_tx_top_adapter #(
        .DEVICE_TYPE(DEVICE_TYPE),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) u_tx_top_adapter (
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
        .pcie_rst_n                    (endpoint_core_rst_n),
        .pcie_clk                      (endpoint_pclk_div2),
        .native_user_define_data_flag  (1'b0),
        .native_mwr32_req              (1'b0),
        .native_mwr32_req_ack          (),
        .native_mwr64_req              (1'b0),
        .native_mwr64_req_ack          (),
        .native_mrd32_req              (1'b0),
        .native_mrd32_req_ack          (),
        .native_mrd64_req              (1'b0),
        .native_mrd64_req_ack          (),
        .native_req_length             (10'd0),
        .native_req_addr               (64'd0),
        .native_req_data               (32'd0),
        .pcie_channel_ready            (pcie_channel_ready),
        .pcie_cdc_fault_pulse          (pcie_cdc_fault_pulse),
        .pcie_cdc_fault_sticky         (pcie_cdc_fault_sticky),
        .cfg_pbus_num                  (cfg_pbus_num),
        .cfg_pbus_dev_num              (cfg_pbus_dev_num),
        .cfg_max_rd_req_size           (cfg_max_rd_req_size),
        .cfg_max_payload_size          (cfg_max_payload_size),
        .axis_slave0_trdy              (endpoint_axis_slave0_tready),
        .axis_slave0_tvld              (endpoint_axis_slave0_tvalid),
        .axis_slave0_tdata             (endpoint_axis_slave0_tdata),
        .axis_slave0_tlast             (endpoint_axis_slave0_tlast),
        .axis_slave0_tuser             (endpoint_axis_slave0_tuser),
        .axis_slave1_trdy              (endpoint_axis_slave1_tready),
        .axis_slave1_tvld              (endpoint_axis_slave1_tvalid),
        .axis_slave1_tdata             (endpoint_axis_slave1_tdata),
        .axis_slave1_tlast             (endpoint_axis_slave1_tlast),
        .axis_slave1_tuser             (endpoint_axis_slave1_tuser),
        .axis_slave2_trdy              (endpoint_axis_slave2_tready),
        .axis_slave2_tvld              (endpoint_axis_slave2_tvalid),
        .axis_slave2_tdata             (endpoint_axis_slave2_tdata),
        .axis_slave2_tlast             (endpoint_axis_slave2_tlast),
        .axis_slave2_tuser             (endpoint_axis_slave2_tuser),
        .bar0_rd_clk_en                (),
        .bar0_rd_addr                  (),
        .bar0_rd_data                  (128'd0),
        .bar2_rd_clk_en                (),
        .bar2_rd_addr                  (),
        .bar2_rd_data                  (128'd0),
        .mrd_tc                        (3'd0),
        .mrd_attr                      (3'd0),
        .mrd_length                    (10'd0),
        .mrd_id                        (16'd0),
        .mrd_tag                       (8'd0),
        .mrd_addr                      (64'd0),
        .cpld_req_vld                  (1'b0),
        .cpld_req_rdy                  (),
        .cpld_tx_rdy                   (),
        .cpld_rcv                      (1'b0),
        .cpld_tag                      (8'd0),
        .tag_full                      (),
        .tx_restart                    (1'b0)
    );
endmodule

`default_nettype wire
