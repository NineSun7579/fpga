`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_mwr32_tx_integration.sv
 * @brief Verify one full-DWORD request through the project bridge and vendor TX.
 *
 * @details
 * The test instantiates the unmodified PG2L50H MWR TX controller directly.
 * It proves only the request/ack and generated AXIS TLP behavior in simulation;
 * it does not prove PCIe link training or a host-memory write.
 *
 * @par Interface contract
 * - The bridge must hold request fields until the vendor ACK is observed.
 * - User-defined data mode is restricted to one DWORD with `req_length=1`.
 * - Only an aligned request with `keep=4'hf` is exercised because the vendor
 *   controller fixes the first and last DWORD byte enables.
 */
module tb_rgb565_pg2l50h_mwr32_tx_integration;
    logic         clk = 1'b0;
    logic         rst_n = 1'b0;
    logic         in_valid = 1'b0;
    logic         in_ready;
    logic [63:0]  in_addr = 64'd0;
    logic [9:0]   in_length_dw = 10'd1;
    logic [31:0]  in_data = 32'd0;
    logic [3:0]   in_keep = 4'd0;
    logic         in_cross_4kb_boundary = 1'b0;
    logic         in_last = 1'b0;
    logic         in_frame_end = 1'b0;
    logic         in_protocol_error = 1'b0;

    logic         mwr32_req;
    logic         mwr32_req_ack;
    logic [9:0]   req_length;
    logic [63:0]  req_addr;
    logic [31:0]  req_data;
    logic [3:0]   req_keep;
    logic         cross_4kb_boundary;
    logic         req_last;
    logic         req_frame_end;
    logic         req_protocol_error;
    logic         bridge_busy;

    logic         mwr64_req_ack;
    logic         rd_en;
    logic [9:0]   rd_length;
    logic         axis_tvld;
    logic [127:0] axis_tdata;
    logic         axis_tlast;
    logic         axis_tuser;
    logic         vendor_busy;
    logic         mwr_tx_hold;
    logic         mwr_tlp_tx;

    integer       axis_beat_count = 0;
    logic [127:0] header_beat = 128'd0;
    logic [127:0] data_beat = 128'd0;
    logic         header_last = 1'b0;
    logic         data_last = 1'b0;

    rgb565_axis4_pcie_mwr_bridge u_bridge (
        .rst_n(rst_n),
        .clk(clk),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_addr(in_addr),
        .in_length_dw(in_length_dw),
        .in_data(in_data),
        .in_keep(in_keep),
        .in_cross_4kb_boundary(in_cross_4kb_boundary),
        .in_last(in_last),
        .in_frame_end(in_frame_end),
        .in_protocol_error(in_protocol_error),
        .mwr32_req(mwr32_req),
        .mwr32_req_ack(mwr32_req_ack),
        .req_length(req_length),
        .req_addr(req_addr),
        .req_data(req_data),
        .req_keep(req_keep),
        .cross_4kb_boundary(cross_4kb_boundary),
        .req_last(req_last),
        .req_frame_end(req_frame_end),
        .req_protocol_error(req_protocol_error),
        .busy(bridge_busy)
    );

    ips2l_pcie_dma_mwr_tx_ctrl u_vendor_tx (
        .clk(clk),
        .rst_n(rst_n),
        .i_cfg_pbus_num(8'h2a),
        .i_cfg_pbus_dev_num(5'h03),
        .i_cfg_max_payload_size(3'd0),
        .i_user_define_data_flag(1'b1),
        .i_mwr32_req(mwr32_req),
        .o_mwr32_req_ack(mwr32_req_ack),
        .i_mwr64_req(1'b0),
        .o_mwr64_req_ack(mwr64_req_ack),
        .i_req_length(req_length),
        .i_req_addr(req_addr),
        .i_req_data(req_data),
        .o_rd_en(rd_en),
        .o_rd_length(rd_length),
        .i_gen_tlp_start(1'b0),
        .i_rd_data(128'd0),
        .i_last_data(1'b0),
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

    // Capture accepted AXIS beats after registered vendor outputs settle.
    always @(posedge clk) begin
        #1ns;
        if (axis_tvld) begin
            if (axis_beat_count == 0) begin
                header_beat = axis_tdata;
                header_last = axis_tlast;
            end else if (axis_beat_count == 1) begin
                data_beat = axis_tdata;
                data_last = axis_tlast;
            end else begin
                $fatal(1, "Unexpected extra vendor AXIS beat");
            end
            axis_beat_count = axis_beat_count + 1;
        end
    end

    initial begin
        #5us;
        $fatal(1, "PG2L50H MWR32 TX integration timeout");
    end

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        @(negedge clk);
        in_addr = 64'h0000_0000_0000_1000;
        in_length_dw = 10'd1;
        in_data = 32'h1122_3344;
        in_keep = 4'hf;
        in_valid = 1'b1;
        if (!in_ready)
            $fatal(1, "Bridge was not ready for the input request");

        @(posedge clk);
        #1ns;
        if (!bridge_busy)
            $fatal(1, "Bridge did not capture the input request");

        @(negedge clk);
        in_valid = 1'b0;
        in_addr = 64'hffff_ffff_ffff_fffc;
        in_length_dw = 10'd7;
        in_data = 32'hdead_beef;
        in_keep = 4'h3;

        while (!mwr32_req) begin
            @(posedge clk);
            #1ns;
        end
        if (req_length !== 10'd1 || req_addr !== 64'h1000 ||
            req_data !== 32'h1122_3344 || req_keep !== 4'hf)
            $fatal(1, "Bridge request fields changed before vendor ACK");

        while (!mwr32_req_ack) begin
            @(posedge clk);
            #1ns;
            if (!mwr32_req || req_length !== 10'd1 ||
                req_addr !== 64'h1000 || req_data !== 32'h1122_3344)
                $fatal(1, "Bridge request was not held while waiting for ACK");
        end

        @(posedge clk);
        #1ns;
        if (mwr32_req || bridge_busy)
            $fatal(1, "Bridge did not release after the canonical ACK");

        wait (axis_beat_count == 2);
        @(posedge clk);
        #1ns;

        if (header_last !== 1'b0 || data_last !== 1'b1)
            $fatal(1, "Vendor header/data TLAST sequence mismatch");
        if (header_beat[31:24] !== 8'h40)
            $fatal(1, "Vendor MWR32 format/type mismatch");
        if (header_beat[9:0] !== 10'd1)
            $fatal(1, "Vendor header length is not one DWORD");
        if (header_beat[39:32] !== 8'h0f)
            $fatal(1, "Vendor first/last DWORD byte enables mismatch");
        if (header_beat[95:64] !== 32'h0000_1000)
            $fatal(1, "Vendor MWR32 address field mismatch");
        if (data_beat[31:0] !== 32'h4433_2211 || data_beat[127:32] !== 96'd0)
            $fatal(1, "Vendor user-defined data byte order mismatch");
        if (rd_en || mwr_tx_hold || vendor_busy || axis_tvld)
            $fatal(1, "Vendor TX did not return to idle");

        repeat (3) @(posedge clk);
        #1ns;
        if (axis_beat_count != 2)
            $fatal(1, "Vendor emitted more than one single-DWORD TLP");

        $display("INFO: full-DWORD bridge to canonical PG2L50H MWR32 TX verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
