`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_pcie_tx_top_adapter.sv
 * @brief Verify camera/native requests through the complete PCIe TX top.
 *
 * @details
 * This test uses non-harmonic camera and PCIe clocks, injects a native
 * user-defined MWR and a camera MWR through the project CDC/arbiter boundary,
 * and checks the AXIS header/data sequence emitted by the unchanged complete
 * `ips2l_pcie_dma_tx_top`. It is intentionally a request/TX integration test;
 * it does not model LTSSM, serial lanes, or RK3568 host memory.
 */
module tb_rgb565_pg2l50h_pcie_tx_top_adapter;
    logic camera_clk = 1'b0;
    logic pcie_clk = 1'b0;
    logic camera_rst_n = 1'b0;
    logic pcie_rst_n = 1'b0;

    logic camera_req = 1'b0;
    logic camera_ack;
    logic camera_ready;
    logic camera_fault_pulse;
    logic camera_fault_sticky;
    logic native_req = 1'b0;
    logic native_ack;
    logic native_user_data = 1'b1;
    logic native_fault_pulse;
    logic native_fault_sticky;
    logic pcie_ready;
    logic pcie_fault_pulse;
    logic pcie_fault_sticky;

    logic axis0_tvld;
    logic [127:0] axis0_tdata;
    logic axis0_tlast;
    logic axis0_tuser;
    logic axis1_tvld;
    logic [127:0] axis1_tdata;
    logic axis1_tlast;
    logic axis1_tuser;
    logic axis2_tvld;
    logic [127:0] axis2_tdata;
    logic axis2_tlast;
    logic axis2_tuser;
    logic bar0_rd_clk_en;
    logic [11:0] bar0_rd_addr;
    logic bar2_rd_clk_en;
    logic [11:0] bar2_rd_addr;
    logic cpld_req_rdy;
    logic cpld_tx_rdy;
    logic tag_full;
    integer beat_count = 0;
    logic [127:0] beats [0:3];
    logic beat_last [0:3];

    rgb565_pg2l50h_pcie_tx_top_adapter u_dut (
        .camera_rst_n                  (camera_rst_n),
        .camera_clk                    (camera_clk),
        .camera_mwr32_req              (camera_req),
        .camera_mwr32_req_ack          (camera_ack),
        .camera_req_length             (10'd1),
        .camera_req_addr               (64'h0000_0000_0000_2000),
        .camera_req_data               (32'h5566_7788),
        .camera_channel_ready          (camera_ready),
        .camera_cdc_fault_pulse        (camera_fault_pulse),
        .camera_cdc_fault_sticky       (camera_fault_sticky),
        .pcie_rst_n                    (pcie_rst_n),
        .pcie_clk                      (pcie_clk),
        .native_user_define_data_flag  (native_user_data),
        .native_mwr32_req              (native_req),
        .native_mwr32_req_ack          (native_ack),
        .native_mwr64_req              (1'b0),
        .native_mwr64_req_ack          (),
        .native_mrd32_req              (1'b0),
        .native_mrd32_req_ack          (),
        .native_mrd64_req              (1'b0),
        .native_mrd64_req_ack          (),
        .native_req_length             (10'd1),
        .native_req_addr               (64'h0000_0000_0000_1000),
        .native_req_data               (32'h1122_3344),
        .pcie_channel_ready            (pcie_ready),
        .pcie_cdc_fault_pulse          (pcie_fault_pulse),
        .pcie_cdc_fault_sticky         (pcie_fault_sticky),
        .cfg_pbus_num                 (8'h2a),
        .cfg_pbus_dev_num             (5'h03),
        .cfg_max_rd_req_size          (3'd0),
        .cfg_max_payload_size         (3'd0),
        .axis_slave0_trdy             (1'b1),
        .axis_slave0_tvld             (axis0_tvld),
        .axis_slave0_tdata            (axis0_tdata),
        .axis_slave0_tlast            (axis0_tlast),
        .axis_slave0_tuser            (axis0_tuser),
        .axis_slave1_trdy             (1'b1),
        .axis_slave1_tvld             (axis1_tvld),
        .axis_slave1_tdata            (axis1_tdata),
        .axis_slave1_tlast            (axis1_tlast),
        .axis_slave1_tuser            (axis1_tuser),
        .axis_slave2_trdy             (1'b1),
        .axis_slave2_tvld             (axis2_tvld),
        .axis_slave2_tdata            (axis2_tdata),
        .axis_slave2_tlast            (axis2_tlast),
        .axis_slave2_tuser            (axis2_tuser),
        .bar0_rd_clk_en               (bar0_rd_clk_en),
        .bar0_rd_addr                 (bar0_rd_addr),
        .bar0_rd_data                 (128'd0),
        .bar2_rd_clk_en               (bar2_rd_clk_en),
        .bar2_rd_addr                 (bar2_rd_addr),
        .bar2_rd_data                 (128'd0),
        .mrd_tc                       (3'd0),
        .mrd_attr                     (3'd0),
        .mrd_length                   (10'd0),
        .mrd_id                       (16'd0),
        .mrd_tag                      (8'd0),
        .mrd_addr                     (64'd0),
        .cpld_req_vld                 (1'b0),
        .cpld_req_rdy                 (cpld_req_rdy),
        .cpld_tx_rdy                  (cpld_tx_rdy),
        .cpld_rcv                     (1'b0),
        .cpld_tag                     (8'd0),
        .tag_full                     (tag_full),
        .tx_restart                   (1'b0)
    );

    always #7ns camera_clk = ~camera_clk;
    always #5ns pcie_clk = ~pcie_clk;

    always @(posedge pcie_clk) begin
        #1ns;
        if (camera_fault_pulse || camera_fault_sticky ||
            pcie_fault_pulse || pcie_fault_sticky)
            $fatal(1, "Unexpected CDC fault during normal TX-top traffic");
        if (axis0_tvld || axis1_tvld)
            $fatal(1, "Inactive CPLD/MRD channel emitted unexpected traffic");
        if (axis2_tvld) begin
            if (beat_count >= 4)
                $fatal(1, "Complete TX top emitted extra MWR beats");
            beats[beat_count] = axis2_tdata;
            beat_last[beat_count] = axis2_tlast;
            beat_count = beat_count + 1;
        end
    end

    initial begin
        #20us;
        $fatal(1, "Complete PCIe TX top adapter timeout");
    end

    initial begin
        repeat (3) @(negedge camera_clk);
        camera_rst_n = 1'b1;
        repeat (2) @(negedge pcie_clk);
        pcie_rst_n = 1'b1;

        wait (camera_ready && pcie_ready);

        @(negedge pcie_clk);
        native_req = 1'b1;
        @(negedge camera_clk);
        camera_req = 1'b1;

        wait (native_ack);
        @(posedge pcie_clk);
        native_req <= 1'b0;
        wait (camera_ack);
        @(posedge camera_clk);
        camera_req <= 1'b0;

        wait (beat_count == 4);
        @(posedge pcie_clk);
        #1ns;

        if (beat_last[0] || !beat_last[1] || beat_last[2] || !beat_last[3])
            $fatal(1, "Complete TX top MWR TLAST sequence mismatch");
        if (beats[0][31:24] !== 8'h40 || beats[0][9:0] !== 10'd1 ||
            beats[0][39:32] !== 8'h0f || beats[0][63:48] !== 16'h2a18 ||
            beats[0][95:64] !== 32'h0000_1000)
            $fatal(1, "Native full-TX-top header mismatch");
        if (beats[1][31:0] !== 32'h4433_2211 || beats[1][127:32] !== 96'd0)
            $fatal(1, "Native full-TX-top data mismatch");
        if (beats[2][31:24] !== 8'h40 || beats[2][9:0] !== 10'd1 ||
            beats[2][39:32] !== 8'h0f || beats[2][63:48] !== 16'h2a18 ||
            beats[2][95:64] !== 32'h0000_2000)
            $fatal(1, "Camera full-TX-top header mismatch");
        if (beats[3][31:0] !== 32'h8877_6655 || beats[3][127:32] !== 96'd0)
            $fatal(1, "Camera full-TX-top data mismatch");

        repeat (5) @(posedge pcie_clk);
        if (beat_count != 4 || native_req || camera_req ||
            pcie_fault_pulse || pcie_fault_sticky)
            $fatal(1, "Complete TX top adapter did not return to idle");

        $display("INFO: camera and native requests reached the complete PCIe TX top");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
