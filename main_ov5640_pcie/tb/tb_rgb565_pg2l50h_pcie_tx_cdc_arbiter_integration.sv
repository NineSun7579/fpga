`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_pcie_tx_cdc_arbiter_integration.sv
 * @brief Verify asynchronous camera MWR32 and native DMA requests at vendor TX.
 *
 * @details
 * A camera request crosses from a non-harmonic DDR application clock into the
 * PCIe clock domain while a native RAM-data request is active. The unchanged
 * MWR TX controller must emit exactly one native TLP followed by exactly one
 * camera user-defined-data TLP. This is a request/TX behavioral test; it does
 * not model link training or host-memory completion.
 */
module tb_rgb565_pg2l50h_pcie_tx_cdc_arbiter_integration;
    logic core_clk = 1'b0;
    logic pcie_clk = 1'b0;
    logic core_rst_n = 1'b0;
    logic pcie_rst_n = 1'b0;

    logic camera_req = 1'b0;
    logic camera_ack;
    logic camera_ready;
    logic camera_fault_pulse;
    logic camera_fault_sticky;

    logic native_req = 1'b0;
    logic native_ack;

    logic pcie_ready;
    logic pcie_fault_pulse;
    logic pcie_fault_sticky;
    logic tx_user_data;
    logic tx_req;
    logic tx_ack;
    logic [9:0] tx_length;
    logic [63:0] tx_addr;
    logic [31:0] tx_data;

    logic mwr64_ack;
    logic rd_en;
    logic [9:0] rd_length;
    logic gen_tlp_start = 1'b0;
    logic axis_tvld;
    logic [127:0] axis_tdata;
    logic axis_tlast;
    logic axis_tuser;
    logic vendor_busy;
    logic mwr_tx_hold;
    logic mwr_tlp_tx;

    integer beat_count = 0;
    logic [127:0] beats [0:3];
    logic beat_last [0:3];

    rgb565_pg2l50h_pcie_tx_cdc_arbiter u_cdc_arbiter (
        .camera_rst_n(core_rst_n),
        .camera_clk(core_clk),
        .camera_mwr32_req(camera_req),
        .camera_mwr32_req_ack(camera_ack),
        .camera_req_length(10'd1),
        .camera_req_addr(64'h0000_0000_0000_2000),
        .camera_req_data(32'h5566_7788),
        .camera_channel_ready(camera_ready),
        .camera_cdc_fault_pulse(camera_fault_pulse),
        .camera_cdc_fault_sticky(camera_fault_sticky),
        .pcie_rst_n(pcie_rst_n),
        .pcie_clk(pcie_clk),
        .native_user_define_data_flag(1'b0),
        .native_mwr32_req(native_req),
        .native_mwr32_req_ack(native_ack),
        .native_mwr64_req(1'b0),
        .native_mwr64_req_ack(),
        .native_mrd32_req(1'b0),
        .native_mrd32_req_ack(),
        .native_mrd64_req(1'b0),
        .native_mrd64_req_ack(),
        .native_req_length(10'd1),
        .native_req_addr(64'h0000_0000_0000_1000),
        .native_req_data(32'h1122_3344),
        .pcie_channel_ready(pcie_ready),
        .pcie_cdc_fault_pulse(pcie_fault_pulse),
        .pcie_cdc_fault_sticky(pcie_fault_sticky),
        .tx_user_define_data_flag(tx_user_data),
        .tx_mwr32_req(tx_req),
        .tx_mwr32_req_ack(tx_ack),
        .tx_mwr64_req(),
        .tx_mwr64_req_ack(1'b0),
        .tx_mrd32_req(),
        .tx_mrd32_req_ack(1'b0),
        .tx_mrd64_req(),
        .tx_mrd64_req_ack(1'b0),
        .tx_req_length(tx_length),
        .tx_req_addr(tx_addr),
        .tx_req_data(tx_data)
    );

    ips2l_pcie_dma_mwr_tx_ctrl u_vendor_tx (
        .clk(pcie_clk),
        .rst_n(pcie_rst_n),
        .i_cfg_pbus_num(8'h2a),
        .i_cfg_pbus_dev_num(5'h03),
        .i_cfg_max_payload_size(3'd0),
        .i_user_define_data_flag(tx_user_data),
        .i_mwr32_req(tx_req),
        .o_mwr32_req_ack(tx_ack),
        .i_mwr64_req(1'b0),
        .o_mwr64_req_ack(mwr64_ack),
        .i_req_length(tx_length),
        .i_req_addr(tx_addr),
        .i_req_data(tx_data),
        .o_rd_en(rd_en),
        .o_rd_length(rd_length),
        .i_gen_tlp_start(gen_tlp_start),
        .i_rd_data({96'd0, 32'h1122_3344}),
        .i_last_data(1'b1),
        .i_axis_slave2_trdy(1'b1),
        .o_axis_slave2_tvld(axis_tvld),
        .o_axis_slave2_tdata(axis_tdata),
        .o_axis_slave2_tlast(axis_tlast),
        .o_axis_slave2_tuser(axis_tuser),
        .o_mwr_tx_busy(vendor_busy),
        .o_mwr_tx_hold(mwr_tx_hold),
        .o_mwr_tlp_tx(mwr_tlp_tx),
        .i_tx_restart(1'b0)
    );

    always #7ns core_clk = ~core_clk;
    always #5ns pcie_clk = ~pcie_clk;

    // The vendor RAM-data mode requires data-valid through its first DATA_TX
    // sampling edge. Camera mode obtains data directly from the request bundle.
    initial begin
        wait (pcie_rst_n);
        wait (rd_en);
        gen_tlp_start = 1'b1;
        wait (mwr_tlp_tx);
        @(posedge pcie_clk);
        #1ns;
        gen_tlp_start = 1'b0;
    end

    always @(posedge core_clk) begin
        #1ns;
        if (camera_fault_pulse || camera_fault_sticky)
            $fatal(1, "Camera CDC fault asserted during normal traffic");
    end

    always @(posedge pcie_clk) begin
        #1ns;
        if (pcie_fault_pulse || pcie_fault_sticky)
            $fatal(1, "PCIe CDC fault asserted during normal traffic");
        if (axis_tvld) begin
            if (beat_count >= 4)
                $fatal(1, "Vendor emitted extra AXIS beats");
            beats[beat_count] = axis_tdata;
            beat_last[beat_count] = axis_tlast;
            beat_count = beat_count + 1;
        end
    end

    initial begin
        #20us;
        $fatal(1, "PCIe TX CDC arbiter integration timeout");
    end

    initial begin
        repeat (3) @(negedge core_clk);
        core_rst_n = 1'b1;
        repeat (2) @(negedge pcie_clk);
        pcie_rst_n = 1'b1;

        wait (camera_ready && pcie_ready);

        @(negedge pcie_clk);
        native_req = 1'b1;
        @(negedge core_clk);
        camera_req = 1'b1;

        wait (native_ack);
        @(posedge pcie_clk);
        native_req <= 1'b0;

        wait (camera_ack);
        @(posedge core_clk);
        camera_req <= 1'b0;

        wait (beat_count == 4);
        @(posedge pcie_clk);
        #1ns;

        if (beat_last[0] || !beat_last[1] || beat_last[2] || !beat_last[3])
            $fatal(1, "Two TLP header/data TLAST sequences mismatch");
        if (beats[0][31:24] !== 8'h40 || beats[0][9:0] !== 10'd1 ||
            beats[0][39:32] !== 8'h0f || beats[0][95:64] !== 32'h0000_1000)
            $fatal(1, "Native TLP header mismatch");
        if (beats[1][31:0] !== 32'h4433_2211 || beats[1][127:32] !== 96'd0)
            $fatal(1, "Native TLP data mismatch");
        if (beats[2][31:24] !== 8'h40 || beats[2][9:0] !== 10'd1 ||
            beats[2][39:32] !== 8'h0f || beats[2][95:64] !== 32'h0000_2000)
            $fatal(1, "Camera TLP header mismatch");
        if (beats[3][31:0] !== 32'h8877_6655 || beats[3][127:32] !== 96'd0)
            $fatal(1, "Camera TLP data mismatch");

        repeat (5) @(posedge pcie_clk);
        if (beat_count != 4 || tx_req || vendor_busy || mwr_tx_hold || rd_en)
            $fatal(1, "CDC/arbiter/vendor path did not return to idle");

        $display("INFO: asynchronous camera and native requests reached canonical MWR TX");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
