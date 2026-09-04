`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_pg2l50h_ddr3_pcie_tx_top_pipeline.sv
 * @brief Verify one behavioral path from OV5640 DVP through the complete PCIe TX top.
 *
 * @details
 * The test drives two camera frames through canonical DDR3 AW/W and AR/R
 * behavioral storage while `io_clk` and `pcie_clk` are non-harmonic. A
 * four-pixel frame produces two full-DWORD MWR32 TLPs. A three-pixel frame
 * produces one full-DWORD TLP, then stops on its partial-DWORD record without
 * acknowledging or emitting it. The policy fault is reported once and only a
 * coordinated reset may recover the path. AXIS0 and AXIS1 remain idle.
 *
 * @warning
 * This test does not instantiate a physical DDR3 core, PCIe link/PHY, board
 * constraints, OV5640 SCCB initialization, or RK3568 host software.
 */
module tb_ov5640_pg2l50h_ddr3_pcie_tx_top_pipeline;
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
    logic         tx_policy_fault_pulse;
    logic         tx_policy_fault_sticky;
    logic         camera_pcie_busy;
    logic         camera_channel_ready;
    logic         camera_cdc_fault_pulse;
    logic         camera_cdc_fault_sticky;
    logic         pcie_channel_ready;
    logic         pcie_cdc_fault_pulse;
    logic         pcie_cdc_fault_sticky;
    logic         axis0_tvld;
    logic [127:0] axis0_tdata;
    logic         axis0_tlast;
    logic         axis0_tuser;
    logic         axis1_tvld;
    logic [127:0] axis1_tdata;
    logic         axis1_tlast;
    logic         axis1_tuser;
    logic         axis2_tvld;
    logic [127:0] axis2_tdata;
    logic         axis2_tlast;
    logic         axis2_tuser;

    logic [127:0] memory [0:255];
    logic         read_pending = 1'b0;
    logic [27:0]  read_addr_reg = 28'd0;
    integer       write_count = 0;
    integer       read_count = 0;
    integer       frame_done_count = 0;
    integer       frame_fault_count = 0;
    integer       policy_fault_count = 0;
    integer       axis_beat_count = 0;
    logic [127:0] axis_beat [0:5];
    logic         axis_last [0:5];

    ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline #(
        .FIFO_ADDR_WIDTH(3),
        .DDR_ADDR_STEP(28'd8),
        .SLOT0_BASE_ADDR(28'd0),
        .SLOT1_BASE_ADDR(28'd128),
        .SLOT_RECORD_CAPACITY(32'd16),
        .PCIE_BASE_ADDR(64'h0000_0000_0000_4000),
        .DDR_REQUEST_ID(4'h3)
    ) u_dut (
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
        .frame_fault_pulse(frame_fault_pulse),
        .tx_policy_fault_pulse(tx_policy_fault_pulse),
        .tx_policy_fault_sticky(tx_policy_fault_sticky),
        .camera_pcie_busy(camera_pcie_busy),
        .camera_channel_ready(camera_channel_ready),
        .camera_cdc_fault_pulse(camera_cdc_fault_pulse),
        .camera_cdc_fault_sticky(camera_cdc_fault_sticky),
        .pcie_rst_n(pcie_rst_n), .pcie_clk(pcie_clk),
        .pcie_channel_ready(pcie_channel_ready),
        .pcie_cdc_fault_pulse(pcie_cdc_fault_pulse),
        .pcie_cdc_fault_sticky(pcie_cdc_fault_sticky),
        .cfg_pbus_num(8'h2a), .cfg_pbus_dev_num(5'h03),
        .cfg_max_rd_req_size(3'd0), .cfg_max_payload_size(3'd0),
        .axis_slave0_trdy(1'b1), .axis_slave0_tvld(axis0_tvld),
        .axis_slave0_tdata(axis0_tdata), .axis_slave0_tlast(axis0_tlast),
        .axis_slave0_tuser(axis0_tuser), .axis_slave1_trdy(1'b1),
        .axis_slave1_tvld(axis1_tvld), .axis_slave1_tdata(axis1_tdata),
        .axis_slave1_tlast(axis1_tlast), .axis_slave1_tuser(axis1_tuser),
        .axis_slave2_trdy(1'b1), .axis_slave2_tvld(axis2_tvld),
        .axis_slave2_tdata(axis2_tdata), .axis_slave2_tlast(axis2_tlast),
        .axis_slave2_tuser(axis2_tuser)
    );

    always #5ns cam_pclk = ~cam_pclk;
    always #7ns io_clk = ~io_clk;
    always #5ns pcie_clk = ~pcie_clk;

    always_comb begin
        axi_awready = ddr_init_done;
        axi_wready = ddr_init_done && axi_awvalid && axi_awready;
        axi_arready = ddr_init_done && !read_pending && !axi_rvalid;
    end

    // Intent: Store one canonical record, including metadata byte lane 4.
    // Invariant: AW and W complete together in this bounded behavioral model.
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

    // Intent: Return one unbackpressured RVALID pulse after each accepted AR.
    // Invariant: A second AR is blocked until the pending response is emitted.
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

    // Intent: Count frame completion and both externally visible fault classes.
    // Invariant: The partial-DWORD frame creates one policy fault and one aggregate fault.
    always_ff @(posedge io_clk or negedge io_rst_n) begin
        if (!io_rst_n) begin
            frame_done_count <= 0;
            frame_fault_count <= 0;
            policy_fault_count <= 0;
        end else begin
            if (frame_done_pulse)
                frame_done_count <= frame_done_count + 1;
            if (frame_fault_pulse)
                frame_fault_count <= frame_fault_count + 1;
            if (tx_policy_fault_pulse)
                policy_fault_count <= policy_fault_count + 1;
        end
    end

    // Intent: Capture accepted MWR traffic and reject activity on inactive channels.
    // Invariant: Three full-DWORD requests produce six AXIS2 beats only.
    always @(posedge pcie_clk) begin
        #1ns;
        if (axis0_tvld || axis1_tvld)
            $fatal(1, "Inactive CPLD/MRD channel emitted unexpected traffic");
        if (axis2_tvld) begin
            if (axis_beat_count >= 6)
                $fatal(1, "Complete TX top emitted extra MWR beats");
            axis_beat[axis_beat_count] = axis2_tdata;
            axis_last[axis_beat_count] = axis2_tlast;
            axis_beat_count = axis_beat_count + 1;
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

    task automatic drive_frame(input integer pixel_count,
                               input logic [15:0] first_pixel);
        begin
            @(negedge cam_pclk);
            cam_vsync = 1'b1;
            @(negedge cam_pclk);
            cam_vsync = 1'b0;
            @(negedge cam_pclk);
            cam_href = 1'b1;
            for (integer index = 0; index < pixel_count; index = index + 1)
                drive_pixel(first_pixel + index);
            @(negedge cam_pclk);
            cam_href = 1'b0;
            @(negedge cam_pclk);
            cam_vsync = 1'b1;
            @(negedge cam_pclk);
            cam_vsync = 1'b0;
        end
    endtask

    task automatic check_request(input integer beat_index,
                                 input integer memory_index,
                                 input logic [31:0] expected_addr);
        begin
            if (axis_last[beat_index] || !axis_last[beat_index + 1] ||
                axis_beat[beat_index][31:24] !== 8'h40 ||
                axis_beat[beat_index][9:0] !== 10'd1 ||
                axis_beat[beat_index][39:32] !== 8'h0f ||
                axis_beat[beat_index][63:48] !== 16'h2a18 ||
                axis_beat[beat_index][95:64] !== expected_addr ||
                axis_beat[beat_index + 1][31:0] !==
                    {memory[memory_index][7:0], memory[memory_index][15:8],
                     memory[memory_index][23:16], memory[memory_index][31:24]} ||
                axis_beat[beat_index + 1][127:32] !== 96'd0)
                $fatal(1, "Complete TX top header/data mismatch at beat %0d", beat_index);
        end
    endtask

    initial begin
        #50us;
        $fatal(1, "OV5640 canonical DDR3 complete PCIe TX top timeout");
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

        drive_frame(4, 16'h1000);
        wait (write_count == 3 && read_count == 3 && frame_done_count == 1);
        wait (axis_beat_count == 4);
        #1ns;
        if (memory[0][35:32] !== 4'hf || memory[8][35:32] !== 4'hf ||
            memory[16][35:32] !== 4'h0 ||
            memory[0][38:36] !== 3'b000 ||
            memory[8][38:36] !== 3'b001 ||
            memory[16][38:36] !== 3'b011)
            $fatal(1, "First-frame DDR3 metadata mismatch");

        drive_frame(3, 16'h2000);
        wait (write_count == 6);
        wait (axis_beat_count == 6 && tx_policy_fault_sticky);
        repeat (5) @(posedge io_clk);
        repeat (5) @(posedge pcie_clk);
        #1ns;

        if (memory[128][35:32] !== 4'hf || memory[136][35:32] !== 4'h3 ||
            memory[144][35:32] !== 4'h0 ||
            memory[128][38:36] !== 3'b000 ||
            memory[136][38:36] !== 3'b001 ||
            memory[144][38:36] !== 3'b011)
            $fatal(1, "Partial-frame DDR3 metadata mismatch");

        check_request(0, 0, 32'h0000_4000);
        check_request(2, 8, 32'h0000_4004);
        check_request(4, 128, 32'h0000_4008);

        if (read_count != 6 || frame_done_count != 2 ||
            frame_fault_count != 1 || policy_fault_count != 1 ||
            !tx_policy_fault_sticky || !camera_pcie_busy ||
            frame_done_slot_id !== 1'b1 ||
            drop_frame_pulse || source_overflow || ddr_read_port_fault_pulse ||
            camera_cdc_fault_pulse || camera_cdc_fault_sticky ||
            pcie_cdc_fault_pulse || pcie_cdc_fault_sticky ||
            ddr_write_busy || ddr_read_busy || axis0_tvld || axis1_tvld ||
            axis2_tvld)
            $fatal(1, "Complete-path mismatch: reads=%0d done=%0d faults=%0d policy=%0d sticky=%b busy=%b slot=%b drop=%b overflow=%b read_fault=%b camera_cdc=%b/%b pcie_cdc=%b/%b ddr_busy=%b/%b axis=%b/%b/%b",
                   read_count, frame_done_count, frame_fault_count,
                   policy_fault_count, tx_policy_fault_sticky,
                   camera_pcie_busy, frame_done_slot_id, drop_frame_pulse,
                   source_overflow, ddr_read_port_fault_pulse,
                   camera_cdc_fault_pulse, camera_cdc_fault_sticky,
                   pcie_cdc_fault_pulse, pcie_cdc_fault_sticky,
                   ddr_write_busy, ddr_read_busy, axis0_tvld,
                   axis1_tvld, axis2_tvld);

        @(negedge cam_pclk);
        cam_rst_n = 1'b0;
        @(negedge io_clk);
        io_rst_n = 1'b0;
        @(negedge pcie_clk);
        pcie_rst_n = 1'b0;
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
        repeat (3) @(posedge io_clk);
        #1ns;
        if (tx_policy_fault_pulse || tx_policy_fault_sticky ||
            camera_pcie_busy || camera_cdc_fault_pulse ||
            camera_cdc_fault_sticky || pcie_cdc_fault_pulse ||
            pcie_cdc_fault_sticky)
            $fatal(1, "Coordinated reset did not clear the policy fail-stop state");

        $display("INFO: DVP, canonical DDR3, CDC, and complete TX top crossed one testbench");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
