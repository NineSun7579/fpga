`default_nettype none

/**
 * @file ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline.sv
 * @brief Connect the OV5640 canonical DDR3 path to the complete PCIe TX top.
 *
 * @details
 * This camera-only integration wrapper joins the project-owned OV5640 and
 * canonical PG2L50H DDR3 pipeline to the complete, unchanged
 * `ips2l_pcie_dma_tx_top` through the audited asynchronous request mailbox.
 * Native DMA, MRD, CPLD, BAR-read data, and TX-restart inputs are inactive in
 * this bounded wrapper; the three AXIS outputs remain visible for integration
 * and verification.
 *
 * @par Interface contract
 * - `cam_*`, `io_*`, and `pcie_*` are three independent clock/reset domains.
 * - A camera request reaches the TX top only when it is one full DWORD,
 *   `req_length` is one, no record protocol error is present, and the request
 *   does not cross a 4 KiB boundary.
 * - A policy-invalid request is not acknowledged and remains fail-stopped in
 *   the IO domain. `tx_policy_fault_pulse` asserts once and
 *   `tx_policy_fault_sticky` remains high until `io_rst_n` is asserted.
 * - Recovery after a policy or CDC fault requires coordinated reset of the
 *   camera, IO, and PCIe domains; this wrapper never replays a request.
 * - `frame_done_pulse` remains a request-path acceptance event. It does not
 *   prove that a TLP reached the link or RK3568 memory.
 *
 * @par Parameters
 * - DDR addresses and slot capacity use the same opaque canonical units as
 *   `ov5640_dvp_rgb565_pg2l50h_pcie_pipeline`.
 * - `PCIE_BASE_ADDR` is a host-visible byte address supplied by integration.
 * - `DEVICE_TYPE` and `ADDR_WIDTH` are passed to the complete PCIe TX top.
 *
 * @par Clock and reset
 * All resets assert asynchronously and must be synchronously released in their
 * own domains. The adapter camera domain is intentionally bound to `io_clk`.
 *
 * @warning
 * This wrapper is behavioral application integration, not board closure. It
 * does not instantiate the DDR3 core or PCIe PHY, configure OV5640 SCCB, assign
 * pins, constrain bundled-data CDC timing, or define RK3568 DMA/cache ownership.
 */
module ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline #(
    parameter integer      FIFO_ADDR_WIDTH = 3,
    parameter logic [27:0] DDR_ADDR_STEP = 28'd0,
    parameter logic [27:0] SLOT0_BASE_ADDR = 28'd0,
    parameter logic [27:0] SLOT1_BASE_ADDR = 28'd0,
    parameter logic [31:0] SLOT_RECORD_CAPACITY = 32'd0,
    parameter logic [63:0] PCIE_BASE_ADDR = 64'd0,
    parameter logic [3:0]  DDR_REQUEST_ID = 4'd0,
    parameter logic [2:0]  DEVICE_TYPE = 3'd0,
    parameter integer      ADDR_WIDTH = 12
) (
    input  wire logic         cam_rst_n,
    input  wire logic         cam_pclk,
    input  wire logic         cam_vsync,
    input  wire logic         cam_href,
    input  wire logic [7:0]   cam_data,
    input  wire logic         io_rst_n,
    input  wire logic         io_clk,
    input  wire logic         ddr_init_done,
    output logic              source_overflow,
    output logic [27:0]       axi_awaddr,
    output logic              axi_awuser_ap,
    output logic [3:0]        axi_awuser_id,
    output logic [3:0]        axi_awlen,
    output logic              axi_awvalid,
    input  wire logic         axi_awready,
    output logic [127:0]      axi_wdata,
    output logic [15:0]       axi_wstrb,
    input  wire logic         axi_wready,
    output logic [27:0]       axi_araddr,
    output logic              axi_aruser_ap,
    output logic [3:0]        axi_aruser_id,
    output logic [3:0]        axi_arlen,
    output logic              axi_arvalid,
    input  wire logic         axi_arready,
    input  wire logic [127:0] axi_rdata,
    input  wire logic [3:0]   axi_rid,
    input  wire logic         axi_rlast,
    input  wire logic         axi_rvalid,
    output logic              ddr_write_busy,
    output logic              ddr_read_busy,
    output logic              ddr_read_port_fault_pulse,
    output logic              drop_frame_pulse,
    output logic              drop_slot_id,
    output logic              frame_done_pulse,
    output logic              frame_done_slot_id,
    output logic              frame_fault_pulse,
    output logic              tx_policy_fault_pulse,
    output logic              tx_policy_fault_sticky,
    output logic              camera_pcie_busy,
    output logic              camera_channel_ready,
    output logic              camera_cdc_fault_pulse,
    output logic              camera_cdc_fault_sticky,
    input  wire logic         pcie_rst_n,
    input  wire logic         pcie_clk,
    output logic              pcie_channel_ready,
    output logic              pcie_cdc_fault_pulse,
    output logic              pcie_cdc_fault_sticky,
    input  wire logic [7:0]   cfg_pbus_num,
    input  wire logic [4:0]   cfg_pbus_dev_num,
    input  wire logic [2:0]   cfg_max_rd_req_size,
    input  wire logic [2:0]   cfg_max_payload_size,
    input  wire logic         axis_slave0_trdy,
    output wire               axis_slave0_tvld,
    output wire [127:0]       axis_slave0_tdata,
    output wire               axis_slave0_tlast,
    output wire               axis_slave0_tuser,
    input  wire logic         axis_slave1_trdy,
    output wire               axis_slave1_tvld,
    output wire [127:0]       axis_slave1_tdata,
    output wire               axis_slave1_tlast,
    output wire               axis_slave1_tuser,
    input  wire logic         axis_slave2_trdy,
    output wire               axis_slave2_tvld,
    output wire [127:0]       axis_slave2_tdata,
    output wire               axis_slave2_tlast,
    output wire               axis_slave2_tuser
);
    logic        pipeline_frame_fault_pulse;
    logic        pipeline_mwr32_req;
    logic        pipeline_mwr32_req_ack;
    logic [9:0]  pipeline_req_length;
    logic [63:0] pipeline_req_addr;
    logic [31:0] pipeline_req_data;
    logic [3:0]  pipeline_req_keep;
    logic        pipeline_cross_4kb_boundary;
    logic        pipeline_req_protocol_error;
    logic        pipeline_pcie_busy;
    logic        adapter_camera_req;
    logic        adapter_camera_ack;
    logic        request_policy_valid;
    logic        request_policy_blocked;
    logic        policy_fault_reported;

    always_comb begin
        request_policy_valid = (pipeline_req_keep == 4'hf) &&
                               (pipeline_req_length == 10'd1) &&
                               !pipeline_req_protocol_error &&
                               !pipeline_cross_4kb_boundary;
        request_policy_blocked = pipeline_mwr32_req &&
                                 !request_policy_valid;
        adapter_camera_req = pipeline_mwr32_req && request_policy_valid;
        pipeline_mwr32_req_ack = adapter_camera_ack;
        camera_pcie_busy = pipeline_pcie_busy;
        frame_fault_pulse = pipeline_frame_fault_pulse |
                            camera_cdc_fault_pulse |
                            tx_policy_fault_pulse;
    end

    // Intent: Report the first policy-invalid request and hold fail-stop state.
    // Invariant: No invalid request is acknowledged or automatically retried.
    always_ff @(posedge io_clk or negedge io_rst_n) begin
        if (!io_rst_n) begin
            tx_policy_fault_pulse <= 1'b0;
            tx_policy_fault_sticky <= 1'b0;
            policy_fault_reported <= 1'b0;
        end else begin
            tx_policy_fault_pulse <= 1'b0;
            if (request_policy_blocked && !policy_fault_reported) begin
                tx_policy_fault_pulse <= 1'b1;
                tx_policy_fault_sticky <= 1'b1;
                policy_fault_reported <= 1'b1;
            end
        end
    end

    ov5640_dvp_rgb565_pg2l50h_pcie_pipeline #(
        .FIFO_ADDR_WIDTH(FIFO_ADDR_WIDTH),
        .DDR_ADDR_STEP(DDR_ADDR_STEP),
        .SLOT0_BASE_ADDR(SLOT0_BASE_ADDR),
        .SLOT1_BASE_ADDR(SLOT1_BASE_ADDR),
        .SLOT_RECORD_CAPACITY(SLOT_RECORD_CAPACITY),
        .PCIE_BASE_ADDR(PCIE_BASE_ADDR),
        .DDR_REQUEST_ID(DDR_REQUEST_ID)
    ) u_camera_pipeline (
        .cam_rst_n(cam_rst_n), .cam_pclk(cam_pclk),
        .cam_vsync(cam_vsync), .cam_href(cam_href), .cam_data(cam_data),
        .io_rst_n(io_rst_n), .io_clk(io_clk),
        .ddr_init_done(ddr_init_done), .source_overflow(source_overflow),
        .axi_awaddr(axi_awaddr), .axi_awuser_ap(axi_awuser_ap),
        .axi_awuser_id(axi_awuser_id), .axi_awlen(axi_awlen),
        .axi_awvalid(axi_awvalid), .axi_awready(axi_awready),
        .axi_wdata(axi_wdata), .axi_wstrb(axi_wstrb),
        .axi_wready(axi_wready), .axi_araddr(axi_araddr),
        .axi_aruser_ap(axi_aruser_ap), .axi_aruser_id(axi_aruser_id),
        .axi_arlen(axi_arlen), .axi_arvalid(axi_arvalid),
        .axi_arready(axi_arready), .axi_rdata(axi_rdata),
        .axi_rid(axi_rid), .axi_rlast(axi_rlast), .axi_rvalid(axi_rvalid),
        .ddr_write_busy(ddr_write_busy), .ddr_read_busy(ddr_read_busy),
        .ddr_read_port_fault_pulse(ddr_read_port_fault_pulse),
        .drop_frame_pulse(drop_frame_pulse), .drop_slot_id(drop_slot_id),
        .frame_done_pulse(frame_done_pulse),
        .frame_done_slot_id(frame_done_slot_id),
        .frame_fault_pulse(pipeline_frame_fault_pulse),
        .mwr32_req(pipeline_mwr32_req),
        .mwr32_req_ack(pipeline_mwr32_req_ack),
        .req_length(pipeline_req_length), .req_addr(pipeline_req_addr),
        .req_data(pipeline_req_data), .req_keep(pipeline_req_keep),
        .cross_4kb_boundary(pipeline_cross_4kb_boundary),
        .req_last(), .req_frame_end(),
        .req_protocol_error(pipeline_req_protocol_error),
        .pcie_busy(pipeline_pcie_busy)
    );

    rgb565_pg2l50h_pcie_tx_top_adapter #(
        .DEVICE_TYPE(DEVICE_TYPE),
        .ADDR_WIDTH(ADDR_WIDTH)
    ) u_tx_top_adapter (
        .camera_rst_n(io_rst_n), .camera_clk(io_clk),
        .camera_mwr32_req(adapter_camera_req),
        .camera_mwr32_req_ack(adapter_camera_ack),
        .camera_req_length(pipeline_req_length),
        .camera_req_addr(pipeline_req_addr),
        .camera_req_data(pipeline_req_data),
        .camera_channel_ready(camera_channel_ready),
        .camera_cdc_fault_pulse(camera_cdc_fault_pulse),
        .camera_cdc_fault_sticky(camera_cdc_fault_sticky),
        .pcie_rst_n(pcie_rst_n), .pcie_clk(pcie_clk),
        .native_user_define_data_flag(1'b0),
        .native_mwr32_req(1'b0), .native_mwr32_req_ack(),
        .native_mwr64_req(1'b0), .native_mwr64_req_ack(),
        .native_mrd32_req(1'b0), .native_mrd32_req_ack(),
        .native_mrd64_req(1'b0), .native_mrd64_req_ack(),
        .native_req_length(10'd0), .native_req_addr(64'd0),
        .native_req_data(32'd0), .pcie_channel_ready(pcie_channel_ready),
        .pcie_cdc_fault_pulse(pcie_cdc_fault_pulse),
        .pcie_cdc_fault_sticky(pcie_cdc_fault_sticky),
        .cfg_pbus_num(cfg_pbus_num), .cfg_pbus_dev_num(cfg_pbus_dev_num),
        .cfg_max_rd_req_size(cfg_max_rd_req_size),
        .cfg_max_payload_size(cfg_max_payload_size),
        .axis_slave0_trdy(axis_slave0_trdy),
        .axis_slave0_tvld(axis_slave0_tvld),
        .axis_slave0_tdata(axis_slave0_tdata),
        .axis_slave0_tlast(axis_slave0_tlast),
        .axis_slave0_tuser(axis_slave0_tuser),
        .axis_slave1_trdy(axis_slave1_trdy),
        .axis_slave1_tvld(axis_slave1_tvld),
        .axis_slave1_tdata(axis_slave1_tdata),
        .axis_slave1_tlast(axis_slave1_tlast),
        .axis_slave1_tuser(axis_slave1_tuser),
        .axis_slave2_trdy(axis_slave2_trdy),
        .axis_slave2_tvld(axis_slave2_tvld),
        .axis_slave2_tdata(axis_slave2_tdata),
        .axis_slave2_tlast(axis_slave2_tlast),
        .axis_slave2_tuser(axis_slave2_tuser),
        .bar0_rd_clk_en(), .bar0_rd_addr(), .bar0_rd_data(128'd0),
        .bar2_rd_clk_en(), .bar2_rd_addr(), .bar2_rd_data(128'd0),
        .mrd_tc(3'd0), .mrd_attr(3'd0), .mrd_length(10'd0),
        .mrd_id(16'd0), .mrd_tag(8'd0), .mrd_addr(64'd0),
        .cpld_req_vld(1'b0), .cpld_req_rdy(), .cpld_tx_rdy(),
        .cpld_rcv(1'b0), .cpld_tag(8'd0), .tag_full(),
        .tx_restart(1'b0)
    );
endmodule

`default_nettype wire
