`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_pg2l50h_ddr3_pcie_loopback.sv
 * @brief Verify OV5640 records through canonical DDR3 AW/W and AR/R boundaries.
 *
 * @details
 * A small DVP frame is processed, stored in a canonical-port memory model,
 * read back without an RREADY signal, crossed from DDR `core_clk` into an
 * asynchronous PCIe `pclk_div2` model, and emitted through the unmodified
 * PG2L50H MWR32 TX controller. The model checks that the DDR record metadata
 * byte survives storage, two TLP header/data pairs are generated, and a
 * zero-payload frame-end record completes locally without a PCIe request.
 *
 * @warning
 * This test does not instantiate the encrypted DDR3 core, PCIe link, PHY,
 * board constraints, OV5640 SCCB configuration, or RK3568 software.
 */
module tb_ov5640_pg2l50h_ddr3_pcie_loopback;
    logic         cam_rst_n = 1'b0;
    logic         cam_pclk = 1'b0;
    logic         cam_vsync = 1'b0;
    logic         cam_href = 1'b0;
    logic [7:0]   cam_data = 8'd0;
    logic         io_rst_n = 1'b0;
    logic         io_clk = 1'b0;
    logic         pcie_rst_n = 1'b0;
    logic         pcie_clk = 1'b0;
    logic         ddr_init_done = 1'b0;
    logic         source_overflow;
    logic [27:0]  axi_awaddr;
    logic         axi_awuser_ap;
    logic [3:0]   axi_awuser_id;
    logic [3:0]   axi_awlen;
    logic         axi_awvalid;
    logic         axi_awready;
    logic [127:0] axi_wdata;
    logic [15:0]  axi_wstrb;
    logic         axi_wready;
    logic [27:0]  axi_araddr;
    logic         axi_aruser_ap;
    logic [3:0]   axi_aruser_id;
    logic [3:0]   axi_arlen;
    logic         axi_arvalid;
    logic         axi_arready;
    logic [127:0] axi_rdata = 128'd0;
    logic [3:0]   axi_rid = 4'd0;
    logic         axi_rlast = 1'b0;
    logic         axi_rvalid = 1'b0;
    logic         ddr_write_busy;
    logic         ddr_read_busy;
    logic         ddr_read_port_fault_pulse;
    logic         drop_frame_pulse;
    logic         drop_slot_id;
    logic         frame_done_pulse;
    logic         frame_done_slot_id;
    logic         frame_fault_pulse;
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
    logic         pcie_busy;

    logic         camera_channel_ready;
    logic         camera_cdc_fault_pulse;
    logic         camera_cdc_fault_sticky;
    logic         pcie_channel_ready;
    logic         pcie_cdc_fault_pulse;
    logic         pcie_cdc_fault_sticky;
    logic         tx_user_define_data_flag;
    logic         tx_mwr32_req;
    logic         tx_mwr32_req_ack;
    logic [9:0]   tx_req_length;
    logic [63:0]  tx_req_addr;
    logic [31:0]  tx_req_data;

    logic         vendor_mwr64_req_ack;
    logic         vendor_rd_en;
    logic [9:0]   vendor_rd_length;
    logic         vendor_axis_tvld;
    logic [127:0] vendor_axis_tdata;
    logic         vendor_axis_tlast;
    logic         vendor_axis_tuser;
    logic         vendor_busy;
    logic         vendor_mwr_tx_hold;
    logic         vendor_mwr_tlp_tx;

    logic [127:0] memory [0:255];
    logic         read_pending = 1'b0;
    logic [27:0]  read_addr_reg = 28'd0;
    integer       write_count = 0;
    integer       read_count = 0;
    integer       mwr_count = 0;
    integer       frame_done_count = 0;
    integer       axis_beat_count = 0;
    logic [127:0] axis_beat [0:3];
    logic         axis_last [0:3];

    ov5640_dvp_rgb565_pg2l50h_pcie_pipeline #(
        .FIFO_ADDR_WIDTH(3), .DDR_ADDR_STEP(28'd8),
        .SLOT0_BASE_ADDR(28'd0), .SLOT1_BASE_ADDR(28'd128),
        .SLOT_RECORD_CAPACITY(32'd16),
        .PCIE_BASE_ADDR(64'h0000_0000_0000_4000),
        .DDR_REQUEST_ID(4'h3)
    ) dut (.*);

    rgb565_pg2l50h_pcie_tx_cdc_arbiter u_tx_cdc_arbiter (
        .camera_rst_n(io_rst_n),
        .camera_clk(io_clk),
        .camera_mwr32_req(mwr32_req),
        .camera_mwr32_req_ack(mwr32_req_ack),
        .camera_req_length(req_length),
        .camera_req_addr(req_addr),
        .camera_req_data(req_data),
        .camera_channel_ready(camera_channel_ready),
        .camera_cdc_fault_pulse(camera_cdc_fault_pulse),
        .camera_cdc_fault_sticky(camera_cdc_fault_sticky),
        .pcie_rst_n(pcie_rst_n),
        .pcie_clk(pcie_clk),
        .native_user_define_data_flag(1'b0),
        .native_mwr32_req(1'b0),
        .native_mwr32_req_ack(),
        .native_mwr64_req(1'b0),
        .native_mwr64_req_ack(),
        .native_mrd32_req(1'b0),
        .native_mrd32_req_ack(),
        .native_mrd64_req(1'b0),
        .native_mrd64_req_ack(),
        .native_req_length(10'd0),
        .native_req_addr(64'd0),
        .native_req_data(32'd0),
        .pcie_channel_ready(pcie_channel_ready),
        .pcie_cdc_fault_pulse(pcie_cdc_fault_pulse),
        .pcie_cdc_fault_sticky(pcie_cdc_fault_sticky),
        .tx_user_define_data_flag(tx_user_define_data_flag),
        .tx_mwr32_req(tx_mwr32_req),
        .tx_mwr32_req_ack(tx_mwr32_req_ack),
        .tx_mwr64_req(),
        .tx_mwr64_req_ack(1'b0),
        .tx_mrd32_req(),
        .tx_mrd32_req_ack(1'b0),
        .tx_mrd64_req(),
        .tx_mrd64_req_ack(1'b0),
        .tx_req_length(tx_req_length),
        .tx_req_addr(tx_req_addr),
        .tx_req_data(tx_req_data)
    );

    ips2l_pcie_dma_mwr_tx_ctrl u_vendor_tx (
        .clk(pcie_clk), .rst_n(pcie_rst_n), .i_cfg_pbus_num(8'h2a),
        .i_cfg_pbus_dev_num(5'h03), .i_cfg_max_payload_size(3'd0),
        .i_user_define_data_flag(tx_user_define_data_flag),
        .i_mwr32_req(tx_mwr32_req),
        .o_mwr32_req_ack(tx_mwr32_req_ack), .i_mwr64_req(1'b0),
        .o_mwr64_req_ack(vendor_mwr64_req_ack), .i_req_length(tx_req_length),
        .i_req_addr(tx_req_addr), .i_req_data(tx_req_data), .o_rd_en(vendor_rd_en),
        .o_rd_length(vendor_rd_length), .i_gen_tlp_start(1'b0),
        .i_rd_data(128'd0), .i_last_data(1'b0), .i_axis_slave2_trdy(1'b1),
        .o_axis_slave2_tvld(vendor_axis_tvld),
        .o_axis_slave2_tdata(vendor_axis_tdata),
        .o_axis_slave2_tlast(vendor_axis_tlast),
        .o_axis_slave2_tuser(vendor_axis_tuser),
        .o_mwr_tx_busy(vendor_busy), .o_mwr_tx_hold(vendor_mwr_tx_hold),
        .o_mwr_tlp_tx(vendor_mwr_tlp_tx), .i_tx_restart(1'b0)
    );

    always #5ns cam_pclk = ~cam_pclk;
    always #7ns io_clk = ~io_clk;
    always #5ns pcie_clk = ~pcie_clk;

    always_comb begin
        axi_awready = ddr_init_done;
        axi_wready = ddr_init_done && axi_awvalid && axi_awready;
        axi_arready = ddr_init_done && !read_pending && !axi_rvalid;
    end

    // Intent: Model one canonical single-beat write per accepted AW command.
    // Invariant: AW and W are accepted together and metadata lane 4 is stored.
    always_ff @(posedge io_clk or negedge io_rst_n) begin
        if (!io_rst_n) begin
            write_count <= 0;
        end else if (axi_awvalid && axi_awready) begin
            if (!axi_wready || axi_awlen != 4'd0 || axi_awuser_id != 4'h3 ||
                axi_awuser_ap || axi_awaddr > 28'd255)
                $fatal(1, "Canonical DDR3 write command mismatch");
            memory[axi_awaddr] <= axi_wdata;
            write_count <= write_count + 1;
        end
    end

    // Intent: Capture each accepted vendor AXIS beat after registered outputs settle.
    // Invariant: Two single-DWORD requests produce exactly header/data/header/data.
    always @(posedge pcie_clk) begin
        #1ns;
        if (vendor_axis_tvld) begin
            if (axis_beat_count > 3)
                $fatal(1, "Vendor TX generated an unexpected extra AXIS beat");
            axis_beat[axis_beat_count] = vendor_axis_tdata;
            axis_last[axis_beat_count] = vendor_axis_tlast;
            axis_beat_count = axis_beat_count + 1;
        end
    end

    // Intent: Return one unbackpressured RVALID pulse after every accepted AR.
    // Invariant: No second AR is accepted until the current pulse is generated.
    always_ff @(posedge io_clk or negedge io_rst_n) begin
        if (!io_rst_n) begin
            read_pending <= 1'b0;
            read_addr_reg <= 28'd0;
            axi_rdata <= 128'd0;
            axi_rid <= 4'd0;
            axi_rlast <= 1'b0;
            axi_rvalid <= 1'b0;
            read_count <= 0;
        end else begin
            axi_rvalid <= 1'b0;
            if (read_pending) begin
                axi_rdata <= memory[read_addr_reg];
                axi_rid <= 4'h3;
                axi_rlast <= 1'b1;
                axi_rvalid <= 1'b1;
                read_pending <= 1'b0;
            end
            if (axi_arvalid && axi_arready) begin
                if (axi_arlen != 4'd0 || axi_aruser_id != 4'h3 ||
                    axi_aruser_ap || axi_araddr > 28'd255)
                    $fatal(1, "Canonical DDR3 read command mismatch");
                read_addr_reg <= axi_araddr;
                read_pending <= 1'b1;
                read_count <= read_count + 1;
            end
        end
    end

    always_ff @(posedge io_clk or negedge io_rst_n) begin
        if (!io_rst_n) begin
            frame_done_count <= 0;
        end else if (frame_done_pulse) begin
            frame_done_count <= frame_done_count + 1;
        end
    end

    task automatic drive_byte(input logic [7:0] value);
        begin
            cam_data = value;
            @(posedge cam_pclk);
        end
    endtask

    task automatic drive_pixel(input logic [15:0] value);
        begin
            drive_byte(value[15:8]);
            drive_byte(value[7:0]);
        end
    endtask

    task automatic drive_frame;
        begin
            @(negedge cam_pclk);
            cam_vsync = 1'b1;
            @(negedge cam_pclk);
            cam_vsync = 1'b0;
            @(negedge cam_pclk);
            cam_href = 1'b1;
            for (integer index = 0; index < 4; index = index + 1)
                drive_pixel(16'h1000 + index);
            @(negedge cam_pclk);
            cam_href = 1'b0;
            @(negedge cam_pclk);
            cam_vsync = 1'b1;
            @(negedge cam_pclk);
            cam_vsync = 1'b0;
        end
    endtask

    task automatic accept_mwr(input integer memory_index,
                              input logic [63:0] expected_addr);
        begin
            wait (mwr32_req);
            #1ns;
            if (!pcie_busy || req_length !== 10'd1 ||
                req_addr !== expected_addr ||
                req_data !== memory[memory_index][31:0] ||
                req_keep !== memory[memory_index][35:32] ||
                req_last !== memory[memory_index][36] ||
                req_frame_end !== memory[memory_index][37] ||
                req_protocol_error !== memory[memory_index][38] ||
                req_keep !== 4'hf || cross_4kb_boundary)
                $fatal(1, "Canonical DDR3 readback to MWR mismatch: busy=%b length=%0d addr=%h/%h data=%h/%h keep=%h/%h last=%b/%b frame=%b/%b error=%b/%b boundary=%b",
                       pcie_busy, req_length, req_addr, expected_addr,
                       req_data, memory[memory_index][31:0], req_keep,
                       memory[memory_index][35:32], req_last,
                       memory[memory_index][36], req_frame_end,
                       memory[memory_index][37], req_protocol_error,
                       memory[memory_index][38], cross_4kb_boundary);
            while (!mwr32_req_ack) begin
                @(posedge io_clk);
                #1ns;
                if (!mwr32_req || req_addr !== expected_addr)
                    $fatal(1, "MWR request changed before vendor ACK");
            end
            while (mwr32_req) begin
                @(posedge io_clk);
                #1ns;
            end
            mwr_count = mwr_count + 1;
        end
    endtask

    initial begin
        #40us;
        $fatal(1, "OV5640 canonical DDR3 PCIe loopback timeout");
    end

    initial begin
        repeat (3) @(posedge cam_pclk);
        repeat (3) @(posedge io_clk);
        repeat (3) @(posedge pcie_clk);
        @(negedge cam_pclk);
        cam_rst_n = 1'b1;
        @(negedge io_clk);
        io_rst_n = 1'b1;
        @(negedge pcie_clk);
        pcie_rst_n = 1'b1;
        wait (camera_channel_ready && pcie_channel_ready);
        repeat (2) @(posedge io_clk);
        @(negedge io_clk);
        ddr_init_done = 1'b1;

        drive_frame();
        wait (write_count == 3);
        repeat (2) @(posedge io_clk);
        #1ns;
        if (memory[0][35:32] !== 4'hf || memory[0][38:36] !== 3'b000 ||
            memory[8][35:32] !== 4'hf || memory[8][38:36] !== 3'b001 ||
            memory[16][35:32] !== 4'h0 || memory[16][38:36] !== 3'b011 ||
            memory[0][39] !== 1'b0 || memory[8][39] !== 1'b0 ||
            memory[16][39] !== 1'b0)
            $fatal(1, "DDR3 record metadata layout mismatch");

        accept_mwr(0, 64'h0000_0000_0000_4000);
        accept_mwr(8, 64'h0000_0000_0000_4004);
        wait (frame_done_count == 1);
        repeat (3) @(posedge io_clk);
        #1ns;
        wait (axis_beat_count == 4);
        repeat (2) @(posedge pcie_clk);
        #1ns;
        if (write_count != 3 || read_count != 3 || mwr_count != 2 ||
            frame_done_slot_id !== 1'b0 || drop_frame_pulse ||
            frame_fault_pulse || ddr_read_port_fault_pulse || source_overflow ||
            mwr32_req || pcie_busy || ddr_write_busy || ddr_read_busy ||
            vendor_busy || vendor_axis_tvld || vendor_rd_en ||
            vendor_mwr_tx_hold || tx_mwr32_req ||
            camera_cdc_fault_pulse || camera_cdc_fault_sticky ||
            pcie_cdc_fault_pulse || pcie_cdc_fault_sticky)
            $fatal(1, "Canonical DDR3 frame completion accounting mismatch");

        if (axis_last[0] !== 1'b0 || axis_last[1] !== 1'b1 ||
            axis_last[2] !== 1'b0 || axis_last[3] !== 1'b1 ||
            axis_beat[0][31:24] !== 8'h40 || axis_beat[2][31:24] !== 8'h40 ||
            axis_beat[0][9:0] !== 10'd1 || axis_beat[2][9:0] !== 10'd1 ||
            axis_beat[0][39:32] !== 8'h0f ||
            axis_beat[2][39:32] !== 8'h0f ||
            axis_beat[0][95:64] !== 32'h0000_4000 ||
            axis_beat[2][95:64] !== 32'h0000_4004 ||
            axis_beat[1][31:0] !== {memory[0][7:0], memory[0][15:8],
                                    memory[0][23:16], memory[0][31:24]} ||
            axis_beat[3][31:0] !== {memory[8][7:0], memory[8][15:8],
                                    memory[8][23:16], memory[8][31:24]} ||
            axis_beat[1][127:32] !== 96'd0 || axis_beat[3][127:32] !== 96'd0)
            $fatal(1, "Vendor MWR32 TLP header/data sequence mismatch");

        $display("INFO: OV5640 frame crossed canonical DDR3 and PG2L50H MWR TX boundaries");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
