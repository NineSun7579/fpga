`default_nettype none

/**
 * @file rgb565_pg2l50h_pcie_tx_cdc_arbiter.sv
 * @brief Cross camera MWR32 transactions into the PCIe domain and arbitrate TX.
 *
 * @details
 * The camera request originates in the DDR3 application `core_clk` domain.
 * A single-outstanding asynchronous mailbox transfers its length/address/data
 * bundle into the PCIe `pclk_div2` domain. The existing project-owned arbiter
 * then shares the complete native DMA request bundle and camera MWR32 request
 * without modifying generated PCIe RTL.
 *
 * @par Interface contract
 * - Camera requests are full-DWORD MWR32 transactions and must remain stable
 *   until `camera_mwr32_req_ack`.
 * - Native requests and all TX request/ACK ports are synchronous to `pcie_clk`.
 * - Native input asserts at most one request type and holds its shared bundle
 *   through the routed ACK.
 * - Mailbox fault outputs require the board integration to invalidate the
 *   active frame/slot and apply a coordinated reset; no request is replayed.
 *
 * @par Clock and reset
 * - Camera domain: `camera_clk`/`camera_rst_n`, normally DDR3 `core_clk`.
 * - PCIe domain: `pcie_clk`/`pcie_rst_n`, normally `pclk_div2`.
 * - Resets assert asynchronously and must be released synchronously in their
 *   local domains. Both clocks must run during channel recovery.
 *
 * @warning
 * This boundary proves transaction CDC and arbitration only. It does not prove
 * TLP transmission, PCIe link state, host memory ownership, IOMMU/cache policy,
 * or bundled-data timing constraints in the placed design.
 */
module rgb565_pg2l50h_pcie_tx_cdc_arbiter (
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
    output logic             tx_user_define_data_flag,
    output logic             tx_mwr32_req,
    input  wire logic        tx_mwr32_req_ack,
    output logic             tx_mwr64_req,
    input  wire logic        tx_mwr64_req_ack,
    output logic             tx_mrd32_req,
    input  wire logic        tx_mrd32_req_ack,
    output logic             tx_mrd64_req,
    input  wire logic        tx_mrd64_req_ack,
    output logic [9:0]       tx_req_length,
    output logic [63:0]      tx_req_addr,
    output logic [31:0]      tx_req_data
);
    logic        pcie_camera_mwr32_req;
    logic        pcie_camera_mwr32_req_ack;
    logic [9:0]  pcie_camera_req_length;
    logic [63:0] pcie_camera_req_addr;
    logic [31:0] pcie_camera_req_data;

    rgb565_pg2l50h_pcie_mwr32_async_mailbox u_camera_mailbox (
        .src_rst_n(camera_rst_n),
        .src_clk(camera_clk),
        .src_mwr32_req(camera_mwr32_req),
        .src_mwr32_req_ack(camera_mwr32_req_ack),
        .src_req_length(camera_req_length),
        .src_req_addr(camera_req_addr),
        .src_req_data(camera_req_data),
        .src_channel_ready(camera_channel_ready),
        .src_fault_pulse(camera_cdc_fault_pulse),
        .src_fault_sticky(camera_cdc_fault_sticky),
        .dst_rst_n(pcie_rst_n),
        .dst_clk(pcie_clk),
        .dst_mwr32_req(pcie_camera_mwr32_req),
        .dst_mwr32_req_ack(pcie_camera_mwr32_req_ack),
        .dst_req_length(pcie_camera_req_length),
        .dst_req_addr(pcie_camera_req_addr),
        .dst_req_data(pcie_camera_req_data),
        .dst_channel_ready(pcie_channel_ready),
        .dst_fault_pulse(pcie_cdc_fault_pulse),
        .dst_fault_sticky(pcie_cdc_fault_sticky)
    );

    rgb565_pg2l50h_pcie_tx_request_arbiter u_tx_arbiter (
        .rst_n(pcie_rst_n),
        .clk(pcie_clk),
        .native_user_define_data_flag(native_user_define_data_flag),
        .native_mwr32_req(native_mwr32_req),
        .native_mwr32_req_ack(native_mwr32_req_ack),
        .native_mwr64_req(native_mwr64_req),
        .native_mwr64_req_ack(native_mwr64_req_ack),
        .native_mrd32_req(native_mrd32_req),
        .native_mrd32_req_ack(native_mrd32_req_ack),
        .native_mrd64_req(native_mrd64_req),
        .native_mrd64_req_ack(native_mrd64_req_ack),
        .native_req_length(native_req_length),
        .native_req_addr(native_req_addr),
        .native_req_data(native_req_data),
        .camera_mwr32_req(pcie_camera_mwr32_req),
        .camera_mwr32_req_ack(pcie_camera_mwr32_req_ack),
        .camera_req_length(pcie_camera_req_length),
        .camera_req_addr(pcie_camera_req_addr),
        .camera_req_data(pcie_camera_req_data),
        .tx_user_define_data_flag(tx_user_define_data_flag),
        .tx_mwr32_req(tx_mwr32_req),
        .tx_mwr32_req_ack(tx_mwr32_req_ack),
        .tx_mwr64_req(tx_mwr64_req),
        .tx_mwr64_req_ack(tx_mwr64_req_ack),
        .tx_mrd32_req(tx_mrd32_req),
        .tx_mrd32_req_ack(tx_mrd32_req_ack),
        .tx_mrd64_req(tx_mrd64_req),
        .tx_mrd64_req_ack(tx_mrd64_req_ack),
        .tx_req_length(tx_req_length),
        .tx_req_addr(tx_req_addr),
        .tx_req_data(tx_req_data)
    );
endmodule

`default_nettype wire
