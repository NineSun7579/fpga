`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_pcie_tx_arbiter_integration.sv
 * @brief Send native and camera MWR32 requests through the unmodified vendor TX.
 *
 * @details
 * Both sources request simultaneously. Reset priority admits a native RAM-data
 * request first, then the waiting camera user-defined request. Four accepted
 * AXIS beats must describe two independent one-DWORD TLPs. This test does not
 * model link training or host-memory completion.
 */
module tb_rgb565_pg2l50h_pcie_tx_arbiter_integration;
    logic clk = 1'b0;
    logic rst_n = 1'b0;

    logic native_req = 1'b0;
    logic native_ack;
    logic camera_req = 1'b0;
    logic camera_ack;
    logic tx_req;
    logic tx_ack;
    logic [9:0] tx_length;
    logic [63:0] tx_addr;
    logic [31:0] tx_data;
    logic tx_user_data;

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

    rgb565_pg2l50h_pcie_tx_request_arbiter u_arbiter (
        .rst_n(rst_n),
        .clk(clk),
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
        .camera_mwr32_req(camera_req),
        .camera_mwr32_req_ack(camera_ack),
        .camera_req_length(10'd1),
        .camera_req_addr(64'h0000_0000_0000_2000),
        .camera_req_data(32'h5566_7788),
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
        .clk(clk),
        .rst_n(rst_n),
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

    always #5ns clk = ~clk;

    // The vendor uses this signal as both RAM-response start and data valid.
    // Keep it high through the first DATA_TX sampling edge, then remove it.
    initial begin
        wait (rst_n);
        wait (rd_en);
        gen_tlp_start = 1'b1;
        wait (mwr_tlp_tx);
        @(posedge clk);
        #1ns;
        gen_tlp_start = 1'b0;
    end

    // The waiting camera request must not change native RAM-data mode early.
    always @(posedge clk) begin
        #1ns;
        if (vendor_busy && camera_req && !camera_ack && tx_user_data)
            $fatal(1, "Camera mode changed before the native MWR completed");
    end

    always @(posedge clk) begin
        #1ns;
        if (axis_tvld) begin
            if (beat_count >= 4)
                $fatal(1, "Vendor emitted extra AXIS beats");
            beats[beat_count] = axis_tdata;
            beat_last[beat_count] = axis_tlast;
            beat_count = beat_count + 1;
        end
    end

    initial begin
        #10us;
        $fatal(1, "PCIe TX arbiter integration timeout");
    end

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        @(negedge clk);
        native_req = 1'b1;
        camera_req = 1'b1;

        wait (native_ack);
        @(posedge clk);
        native_req <= 1'b0;

        wait (camera_ack);
        @(posedge clk);
        camera_req <= 1'b0;

        wait (beat_count == 4);
        @(posedge clk);
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
        if (rd_en || mwr_tx_hold || vendor_busy || axis_tvld || tx_req)
            $fatal(1, "Vendor or arbiter did not return to idle");

        repeat (3) @(posedge clk);
        if (beat_count != 4)
            $fatal(1, "Unexpected additional TLP after both requests completed");

        $display("INFO: native and camera requests shared the canonical PG2L50H MWR TX");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
