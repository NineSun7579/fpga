`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv
 * @brief Verify the project TX path at the PCIe Endpoint AXIS boundary.
 *
 * @details
 * The test connects the project-owned camera TX boundary to an Endpoint stub
 * whose ports match the relevant `pcie_test` clock, reset, link-status, and
 * AXIS slave subset. It verifies reset ownership, transparent link telemetry,
 * AXIS2 backpressure, and the camera MWR32 header/data sequence. The stub does
 * not model the PCIe hard block, LTSSM, serial lanes, or RK3568 host memory.
 */
module tb_rgb565_pg2l50h_pcie_endpoint_axis_boundary;
    logic camera_clk = 1'b0;
    logic endpoint_pclk_div2 = 1'b0;
    logic camera_rst_n = 1'b0;
    logic endpoint_core_rst_n = 1'b0;
    logic endpoint_smlh_link_up = 1'b0;
    logic endpoint_rdlh_link_up = 1'b0;
    logic endpoint_axis2_ready = 1'b1;

    logic camera_req = 1'b0;
    logic camera_ack;
    logic camera_ready;
    logic camera_fault_pulse;
    logic camera_fault_sticky;
    logic pcie_ready;
    logic pcie_fault_pulse;
    logic pcie_fault_sticky;
    logic observed_smlh_link_up;
    logic observed_rdlh_link_up;

    logic axis0_tready;
    logic axis0_tvalid;
    logic [127:0] axis0_tdata;
    logic axis0_tlast;
    logic axis0_tuser;
    logic axis1_tready;
    logic axis1_tvalid;
    logic [127:0] axis1_tdata;
    logic axis1_tlast;
    logic axis1_tuser;
    logic axis2_tready;
    logic axis2_tvalid;
    logic [127:0] axis2_tdata;
    logic axis2_tlast;
    logic axis2_tuser;

    integer beat_count = 0;
    logic [127:0] beats [0:1];
    logic beat_last [0:1];
    logic stalled_data_seen = 1'b0;
    logic [127:0] stalled_data;

    rgb565_pg2l50h_pcie_endpoint_axis_boundary u_dut (
        .camera_rst_n                 (camera_rst_n),
        .camera_clk                   (camera_clk),
        .camera_mwr32_req             (camera_req),
        .camera_mwr32_req_ack         (camera_ack),
        .camera_req_length            (10'd1),
        .camera_req_addr              (64'h0000_0000_0000_2400),
        .camera_req_data              (32'h5566_7788),
        .camera_channel_ready         (camera_ready),
        .camera_cdc_fault_pulse       (camera_fault_pulse),
        .camera_cdc_fault_sticky      (camera_fault_sticky),
        .endpoint_pclk_div2           (endpoint_pclk_div2),
        .endpoint_core_rst_n          (endpoint_core_rst_n),
        .endpoint_smlh_link_up        (endpoint_smlh_link_up),
        .endpoint_rdlh_link_up        (endpoint_rdlh_link_up),
        .observed_smlh_link_up        (observed_smlh_link_up),
        .observed_rdlh_link_up        (observed_rdlh_link_up),
        .pcie_channel_ready           (pcie_ready),
        .pcie_cdc_fault_pulse         (pcie_fault_pulse),
        .pcie_cdc_fault_sticky        (pcie_fault_sticky),
        .cfg_pbus_num                 (8'h2a),
        .cfg_pbus_dev_num             (5'h03),
        .cfg_max_rd_req_size          (3'd0),
        .cfg_max_payload_size         (3'd0),
        .endpoint_axis_slave0_tready  (axis0_tready),
        .endpoint_axis_slave0_tvalid  (axis0_tvalid),
        .endpoint_axis_slave0_tdata   (axis0_tdata),
        .endpoint_axis_slave0_tlast   (axis0_tlast),
        .endpoint_axis_slave0_tuser   (axis0_tuser),
        .endpoint_axis_slave1_tready  (axis1_tready),
        .endpoint_axis_slave1_tvalid  (axis1_tvalid),
        .endpoint_axis_slave1_tdata   (axis1_tdata),
        .endpoint_axis_slave1_tlast   (axis1_tlast),
        .endpoint_axis_slave1_tuser   (axis1_tuser),
        .endpoint_axis_slave2_tready  (axis2_tready),
        .endpoint_axis_slave2_tvalid  (axis2_tvalid),
        .endpoint_axis_slave2_tdata   (axis2_tdata),
        .endpoint_axis_slave2_tlast   (axis2_tlast),
        .endpoint_axis_slave2_tuser   (axis2_tuser)
    );

    pcie_endpoint_axis_subset_stub u_endpoint_stub (
        .model_pclk_div2          (endpoint_pclk_div2),
        .model_core_rst_n         (endpoint_core_rst_n),
        .model_smlh_link_up       (endpoint_smlh_link_up),
        .model_rdlh_link_up       (endpoint_rdlh_link_up),
        .model_axis_slave2_tready (endpoint_axis2_ready),
        .axis_slave0_tready       (axis0_tready),
        .axis_slave0_tvalid       (axis0_tvalid),
        .axis_slave0_tdata        (axis0_tdata),
        .axis_slave0_tlast        (axis0_tlast),
        .axis_slave0_tuser        (axis0_tuser),
        .axis_slave1_tready       (axis1_tready),
        .axis_slave1_tvalid       (axis1_tvalid),
        .axis_slave1_tdata        (axis1_tdata),
        .axis_slave1_tlast        (axis1_tlast),
        .axis_slave1_tuser        (axis1_tuser),
        .axis_slave2_tready       (axis2_tready),
        .axis_slave2_tvalid       (axis2_tvalid),
        .axis_slave2_tdata        (axis2_tdata),
        .axis_slave2_tlast        (axis2_tlast),
        .axis_slave2_tuser        (axis2_tuser)
    );

    always #7ns camera_clk = ~camera_clk;
    always #5ns endpoint_pclk_div2 = ~endpoint_pclk_div2;

    // Intent: Check the exact ready/valid handshake seen by the Endpoint stub.
    // Invariant: AXIS0/1 stay idle and stalled AXIS2 payload remains stable.
    always @(posedge endpoint_pclk_div2) begin
        if (camera_fault_pulse || camera_fault_sticky ||
            pcie_fault_pulse || pcie_fault_sticky)
            $fatal(1, "Unexpected CDC fault at Endpoint boundary");
        if (axis0_tvalid || axis1_tvalid)
            $fatal(1, "Inactive AXIS0/1 emitted traffic at Endpoint boundary");

        if (axis2_tvalid && !axis2_tready) begin
            if (!stalled_data_seen) begin
                stalled_data_seen = 1'b1;
                stalled_data = axis2_tdata;
            end else if (axis2_tdata !== stalled_data || !axis2_tlast)
                $fatal(1, "AXIS2 data changed while Endpoint applied backpressure");
        end

        if (axis2_tvalid && axis2_tready) begin
            if (beat_count >= 2)
                $fatal(1, "Endpoint received extra AXIS2 beats");
            beats[beat_count] = axis2_tdata;
            beat_last[beat_count] = axis2_tlast;
            beat_count = beat_count + 1;
        end
    end

    initial begin
        #20us;
        $fatal(1, "PCIe Endpoint AXIS boundary timeout");
    end

    initial begin
        repeat (3) @(negedge camera_clk);
        camera_rst_n = 1'b1;
        repeat (3) @(posedge endpoint_pclk_div2);
        if (camera_ready || pcie_ready)
            $fatal(1, "Endpoint-owned reset did not hold the TX path inactive");

        @(negedge endpoint_pclk_div2);
        endpoint_core_rst_n = 1'b1;
        wait (camera_ready && pcie_ready);

        if (observed_smlh_link_up || observed_rdlh_link_up)
            $fatal(1, "Link telemetry did not reflect the Endpoint inputs");

        // Link state is observation only; Endpoint ready provides TX flow control.
        @(negedge camera_clk);
        camera_req = 1'b1;

        // The generated TX controller requires ready to leave IDLE. Remove it
        // after the header handshake so the payload is the stalled beat.
        wait (axis2_tvalid);
        wait (beat_count == 1);
        @(negedge endpoint_pclk_div2);
        endpoint_axis2_ready = 1'b0;
        repeat (3) @(posedge endpoint_pclk_div2);
        if (!stalled_data_seen || beat_count != 1)
            $fatal(1, "Endpoint backpressure did not stall the AXIS2 payload");

        @(negedge endpoint_pclk_div2);
        endpoint_smlh_link_up = 1'b1;
        endpoint_rdlh_link_up = 1'b1;
        endpoint_axis2_ready = 1'b1;

        repeat (20) @(posedge endpoint_pclk_div2);
        if (beat_count != 2)
            $fatal(1, "Endpoint did not consume both AXIS2 beats: count=%0d", beat_count);
        wait (camera_ack);
        $display("INFO: camera request accepted by project TX boundary");
        @(posedge camera_clk);
        camera_req <= 1'b0;
        @(posedge endpoint_pclk_div2);
        #1ns;

        if (!observed_smlh_link_up || !observed_rdlh_link_up)
            $fatal(1, "Link telemetry did not track Endpoint link-up status");
        if (beat_last[0] || !beat_last[1])
            $fatal(1, "Endpoint AXIS2 TLAST sequence mismatch");
        if (beats[0][31:24] !== 8'h40 || beats[0][9:0] !== 10'd1 ||
            beats[0][39:32] !== 8'h0f || beats[0][63:48] !== 16'h2a18 ||
            beats[0][95:64] !== 32'h0000_2400)
            $fatal(1, "Endpoint AXIS2 camera header mismatch");
        if (beats[1][31:0] !== 32'h8877_6655 ||
            beats[1][127:32] !== 96'd0)
            $fatal(1, "Endpoint AXIS2 camera data mismatch");

        repeat (5) @(posedge endpoint_pclk_div2);
        if (beat_count != 2 || camera_req)
            $fatal(1, "Endpoint AXIS boundary did not return to idle");

        $display("INFO: camera MWR32 reached the PCIe Endpoint AXIS2 boundary");
        $display("TEST PASS");
        $finish;
    end
endmodule

/**
 * @brief Minimal behavioral model of the `pcie_test` TX-facing subset.
 *
 * @details
 * Signal directions intentionally match the generated Endpoint: AXIS slave
 * ready is produced by the Endpoint while valid/data/last/user are consumed.
 */
module pcie_endpoint_axis_subset_stub (
    input  wire logic         model_pclk_div2,
    input  wire logic         model_core_rst_n,
    input  wire logic         model_smlh_link_up,
    input  wire logic         model_rdlh_link_up,
    input  wire logic         model_axis_slave2_tready,
    output wire               axis_slave0_tready,
    input  wire logic         axis_slave0_tvalid,
    input  wire logic [127:0] axis_slave0_tdata,
    input  wire logic         axis_slave0_tlast,
    input  wire logic         axis_slave0_tuser,
    output wire               axis_slave1_tready,
    input  wire logic         axis_slave1_tvalid,
    input  wire logic [127:0] axis_slave1_tdata,
    input  wire logic         axis_slave1_tlast,
    input  wire logic         axis_slave1_tuser,
    output wire               axis_slave2_tready,
    input  wire logic         axis_slave2_tvalid,
    input  wire logic [127:0] axis_slave2_tdata,
    input  wire logic         axis_slave2_tlast,
    input  wire logic         axis_slave2_tuser
);
    assign axis_slave0_tready = 1'b1;
    assign axis_slave1_tready = 1'b1;
    assign axis_slave2_tready = model_axis_slave2_tready;

    // Keep the generated-Endpoint ownership signals visible to lint/elaboration.
    wire unused_endpoint_state = model_pclk_div2 ^ model_core_rst_n ^
                                 model_smlh_link_up ^ model_rdlh_link_up ^
                                 axis_slave0_tvalid ^ axis_slave0_tlast ^
                                 axis_slave0_tuser ^ axis_slave1_tvalid ^
                                 axis_slave1_tlast ^ axis_slave1_tuser ^
                                 axis_slave2_tvalid ^ axis_slave2_tlast ^
                                 axis_slave2_tuser ^ ^axis_slave0_tdata ^
                                 ^axis_slave1_tdata ^ ^axis_slave2_tdata;
endmodule

`default_nettype wire
