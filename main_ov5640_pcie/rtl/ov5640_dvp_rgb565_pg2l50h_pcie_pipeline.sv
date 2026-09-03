`default_nettype none

/**
 * @file ov5640_dvp_rgb565_pg2l50h_pcie_pipeline.sv
 * @brief Connect the OV5640 frame path to canonical PG2L50H DDR3 user ports.
 *
 * @details
 * This integration layer combines the vendor-independent OV5640, frame-slot,
 * and PCIe request pipeline with the audited PG2L50H DDR3 AW/W and AR/R user
 * interfaces. Every normalized 32-bit record is stored in one 128-bit DDR3 beat;
 * byte lane 4 preserves record metadata for exact readback. The PCIe side remains
 * the audited MWR32 request/ack boundary consumed by the vendor TX controller.
 *
 * The module does not instantiate generated DDR3 or PCIe IP, assign physical
 * pins, configure OV5640 SCCB registers, or select host memory addresses.
 *
 * @par Interface contract
 * - `cam_*` belongs to the OV5640 pixel-clock domain; all DDR3 and PCIe request
 *   ports belong to `io_clk`, which must be the DDR3 application `core_clk`.
 * - DDR3 initialization is synchronized inside each canonical adapter; neither
 *   read nor write commands are admitted before the synchronized ready level.
 * - Each record uses one ARLEN/AWLEN zero transaction and one 128-bit beat.
 * - DDR3 read data is buffered because the canonical IP exposes no RREADY.
 * - `mwr32_req` and request fields remain stable until `mwr32_req_ack`.
 * - `frame_fault_pulse` includes frame-management faults and canonical read-port
 *   faults; `ddr_read_port_fault_pulse` identifies the latter directly.
 *
 * @par Parameters
 * - `DDR_ADDR_STEP` is the canonical address increment per stored record. Zero is
 *   rejected so board integration must choose the unit from authoritative data.
 * - Slot bases and capacity are expressed in the same opaque canonical units.
 * - `PCIE_BASE_ADDR` is the first host-visible byte address for MWR requests.
 *
 * @par Clock and reset
 * - Camera clock/reset: `cam_pclk` and `cam_rst_n`.
 * - DDR3/PCIe application clock/reset: `io_clk` and `io_rst_n`.
 * - Both resets assert asynchronously and must be released synchronously in their
 *   respective domains by the board-level reset tree.
 *
 * @par Assumptions
 * - The board-level integration keeps `ddr_init_done` asserted during traffic.
 * - Slot address ranges do not overlap and fit the physical DDR3 configuration.
 * - PCIe request clocking matches the vendor MWR TX controller clock domain.
 *
 * @warning
 * This is a synthesizable application-boundary integration, not board closure.
 * DDR3 address units, pin constraints, timing, PCIe link training, host buffer
 * ownership, and final-DWORD byte-enable policy still require board evidence.
 */
module ov5640_dvp_rgb565_pg2l50h_pcie_pipeline #(
    parameter integer      FIFO_ADDR_WIDTH = 3,
    parameter logic [27:0] DDR_ADDR_STEP = 28'd0,
    parameter logic [27:0] SLOT0_BASE_ADDR = 28'd0,
    parameter logic [27:0] SLOT1_BASE_ADDR = 28'd0,
    parameter logic [31:0] SLOT_RECORD_CAPACITY = 32'd0,
    parameter logic [63:0] PCIE_BASE_ADDR = 64'd0,
    parameter logic [3:0]  DDR_REQUEST_ID = 4'd0
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
    logic         ddr_write_valid;
    logic         ddr_write_ready;
    logic         ddr_write_slot_id;
    logic [27:0]  ddr_write_addr;
    logic [3:0]   ddr_write_awlen;
    logic [127:0] ddr_write_data;
    logic [15:0]  ddr_write_strb;
    logic         ddr_write_last;
    logic         ddr_write_frame_end;
    logic         ddr_write_protocol_error;

    logic         ddr_read_cmd_valid;
    logic         ddr_read_cmd_ready;
    logic [27:0]  ddr_read_cmd_addr;
    logic         ddr_read_valid;
    logic         ddr_read_ready;
    logic [31:0]  ddr_read_data;
    logic [3:0]   ddr_read_keep;
    logic         ddr_read_last;
    logic         ddr_read_frame_end;
    logic         ddr_read_protocol_error;
    logic         pipeline_frame_fault_pulse;

    initial begin : p_validate_parameters
        if (DDR_ADDR_STEP == 28'd0)
            $fatal(1, "PG2L50H integration requires a non-zero DDR_ADDR_STEP");
        if (SLOT_RECORD_CAPACITY == 32'd0)
            $fatal(1, "PG2L50H integration requires non-zero slot capacity");
        if (SLOT0_BASE_ADDR == SLOT1_BASE_ADDR)
            $fatal(1, "PG2L50H integration requires distinct slot bases");
    end

    always_comb begin
        frame_fault_pulse = pipeline_frame_fault_pulse |
                            ddr_read_port_fault_pulse;
    end

    ov5640_dvp_rgb565_ddr3_pcie_pipeline #(
        .FIFO_ADDR_WIDTH(FIFO_ADDR_WIDTH),
        .TOKEN_ADDR_STEP(DDR_ADDR_STEP),
        .SLOT0_BASE_ADDR(SLOT0_BASE_ADDR),
        .SLOT1_BASE_ADDR(SLOT1_BASE_ADDR),
        .SLOT_RECORD_CAPACITY(SLOT_RECORD_CAPACITY),
        .PCIE_BASE_ADDR(PCIE_BASE_ADDR)
    ) u_pipeline (
        .in_rst_n(cam_rst_n), .cam_pclk(cam_pclk), .cam_vsync(cam_vsync),
        .cam_href(cam_href), .cam_data(cam_data), .io_rst_n(io_rst_n),
        .io_clk(io_clk), .source_overflow(source_overflow),
        .ddr_write_valid(ddr_write_valid), .ddr_write_ready(ddr_write_ready),
        .ddr_write_slot_id(ddr_write_slot_id),
        .ddr_write_addr(ddr_write_addr), .ddr_write_awlen(ddr_write_awlen),
        .ddr_write_data(ddr_write_data), .ddr_write_strb(ddr_write_strb),
        .ddr_write_last(ddr_write_last),
        .ddr_write_frame_end(ddr_write_frame_end),
        .ddr_write_protocol_error(ddr_write_protocol_error),
        .ddr_read_cmd_valid(ddr_read_cmd_valid),
        .ddr_read_cmd_ready(ddr_read_cmd_ready),
        .ddr_read_cmd_addr(ddr_read_cmd_addr), .ddr_read_valid(ddr_read_valid),
        .ddr_read_ready(ddr_read_ready), .ddr_read_data(ddr_read_data),
        .ddr_read_keep(ddr_read_keep), .ddr_read_last(ddr_read_last),
        .ddr_read_frame_end(ddr_read_frame_end),
        .ddr_read_protocol_error(ddr_read_protocol_error),
        .drop_frame_pulse(drop_frame_pulse), .drop_slot_id(drop_slot_id),
        .frame_done_pulse(frame_done_pulse),
        .frame_done_slot_id(frame_done_slot_id),
        .frame_fault_pulse(pipeline_frame_fault_pulse),
        .mwr32_req(mwr32_req), .mwr32_req_ack(mwr32_req_ack),
        .req_length(req_length), .req_addr(req_addr), .req_data(req_data),
        .req_keep(req_keep), .cross_4kb_boundary(cross_4kb_boundary),
        .req_last(req_last), .req_frame_end(req_frame_end),
        .req_protocol_error(req_protocol_error), .pcie_busy(pcie_busy)
    );

    rgb565_pg2l50h_ddr3_write_adapter #(
        .REQUEST_ID(DDR_REQUEST_ID)
    ) u_ddr_write_adapter (
        .rst_n(io_rst_n), .clk(io_clk), .ddr_init_done(ddr_init_done),
        .in_valid(ddr_write_valid), .in_ready(ddr_write_ready),
        .in_addr(ddr_write_addr), .in_data(ddr_write_data),
        .in_strb(ddr_write_strb), .axi_awaddr(axi_awaddr),
        .axi_awuser_ap(axi_awuser_ap), .axi_awuser_id(axi_awuser_id),
        .axi_awlen(axi_awlen), .axi_awvalid(axi_awvalid),
        .axi_awready(axi_awready), .axi_wdata(axi_wdata),
        .axi_wstrb(axi_wstrb), .axi_wready(axi_wready),
        .busy(ddr_write_busy)
    );

    rgb565_pg2l50h_ddr3_read_adapter #(
        .REQUEST_ID(DDR_REQUEST_ID)
    ) u_ddr_read_adapter (
        .rst_n(io_rst_n), .clk(io_clk), .ddr_init_done(ddr_init_done),
        .in_valid(ddr_read_cmd_valid), .in_ready(ddr_read_cmd_ready),
        .in_addr(ddr_read_cmd_addr), .axi_araddr(axi_araddr),
        .axi_aruser_ap(axi_aruser_ap), .axi_aruser_id(axi_aruser_id),
        .axi_arlen(axi_arlen), .axi_arvalid(axi_arvalid),
        .axi_arready(axi_arready), .axi_rdata(axi_rdata),
        .axi_rid(axi_rid), .axi_rlast(axi_rlast),
        .axi_rvalid(axi_rvalid), .out_valid(ddr_read_valid),
        .out_ready(ddr_read_ready), .out_data(ddr_read_data),
        .out_keep(ddr_read_keep), .out_last(ddr_read_last),
        .out_frame_end(ddr_read_frame_end),
        .out_protocol_error(ddr_read_protocol_error),
        .port_fault_pulse(ddr_read_port_fault_pulse),
        .busy(ddr_read_busy)
    );
endmodule

`default_nettype wire
