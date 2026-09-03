`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_pg2l50h_ddr3_write_path.sv
 * @brief Verify normalized frame records through the canonical DDR3 write adapter.
 *
 * @details
 * The test connects the existing slotted write descriptor directly to the
 * PG2L50H write adapter. It checks that frame release follows the DDR3 user
 * port data-consume edge, not internal pre-capture or AW acceptance.
 */
module tb_rgb565_axis4_pg2l50h_ddr3_write_path;
    logic         rst_n = 1'b0;
    logic         clk = 1'b0;
    logic         ddr_init_done = 1'b0;

    logic         frame_alloc_valid = 1'b0;
    logic         frame_alloc_ready;
    logic         frame_alloc_slot_id = 1'b0;
    logic [27:0]  frame_alloc_base_addr = 28'd0;
    logic [31:0]  frame_alloc_record_capacity = 32'd0;
    logic         in_valid = 1'b0;
    logic         in_ready;
    logic [31:0]  in_data = 32'd0;
    logic [3:0]   in_keep = 4'd0;
    logic         in_last = 1'b0;
    logic         in_frame_end = 1'b0;
    logic         in_protocol_error = 1'b0;

    logic         write_valid;
    logic         write_ready;
    logic         write_slot_id;
    logic [27:0]  write_addr;
    logic [3:0]   write_awlen;
    logic [127:0] write_data;
    logic [15:0]  write_strb;
    logic         write_last;
    logic         write_frame_end;
    logic         write_protocol_error;

    logic [27:0]  axi_awaddr;
    logic         axi_awuser_ap;
    logic [3:0]   axi_awuser_id;
    logic [3:0]   axi_awlen;
    logic         axi_awvalid;
    logic         axi_awready = 1'b0;
    logic [127:0] axi_wdata;
    logic [15:0]  axi_wstrb;
    logic         axi_wready = 1'b0;
    logic         adapter_busy;

    integer aw_count = 0;
    integer write_complete_count = 0;

    rgb565_axis4_ddr3_write_descriptor #(
        .ADDR_STEP(28'd1)
    ) u_writer (
        .rst_n(rst_n),
        .clk(clk),
        .frame_alloc_valid(frame_alloc_valid),
        .frame_alloc_ready(frame_alloc_ready),
        .frame_alloc_slot_id(frame_alloc_slot_id),
        .frame_alloc_base_addr(frame_alloc_base_addr),
        .frame_alloc_record_capacity(frame_alloc_record_capacity),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(in_data),
        .in_keep(in_keep),
        .in_last(in_last),
        .in_frame_end(in_frame_end),
        .in_protocol_error(in_protocol_error),
        .write_valid(write_valid),
        .write_ready(write_ready),
        .write_slot_id(write_slot_id),
        .write_addr(write_addr),
        .write_awlen(write_awlen),
        .write_data(write_data),
        .write_strb(write_strb),
        .write_last(write_last),
        .write_frame_end(write_frame_end),
        .write_protocol_error(write_protocol_error)
    );

    rgb565_pg2l50h_ddr3_write_adapter #(
        .REQUEST_ID(4'h2)
    ) u_adapter (
        .rst_n(rst_n),
        .clk(clk),
        .ddr_init_done(ddr_init_done),
        .in_valid(write_valid),
        .in_ready(write_ready),
        .in_addr(write_addr),
        .in_data(write_data),
        .in_strb(write_strb),
        .axi_awaddr(axi_awaddr),
        .axi_awuser_ap(axi_awuser_ap),
        .axi_awuser_id(axi_awuser_id),
        .axi_awlen(axi_awlen),
        .axi_awvalid(axi_awvalid),
        .axi_awready(axi_awready),
        .axi_wdata(axi_wdata),
        .axi_wstrb(axi_wstrb),
        .axi_wready(axi_wready),
        .busy(adapter_busy)
    );

    always #5ns clk = ~clk;

    always @(posedge clk) begin
        if (axi_awvalid && axi_awready)
            aw_count = aw_count + 1;
        if (write_valid && write_ready)
            write_complete_count = write_complete_count + 1;
    end

    task automatic allocate_frame(input logic slot_id,
                                  input logic [27:0] base_addr);
        begin
            wait (frame_alloc_ready);
            @(negedge clk);
            frame_alloc_slot_id = slot_id;
            frame_alloc_base_addr = base_addr;
            frame_alloc_record_capacity = 32'd4;
            frame_alloc_valid = 1'b1;
            @(posedge clk);
            #1ns;
            frame_alloc_valid = 1'b0;
        end
    endtask

    task automatic stage_frame_record(input logic [31:0] data,
                                      input logic [3:0] keep);
        begin
            wait (in_ready);
            @(negedge clk);
            in_data = data;
            in_keep = keep;
            in_last = 1'b1;
            in_frame_end = 1'b1;
            in_protocol_error = 1'b0;
            in_valid = 1'b1;
            @(posedge clk);
            #1ns;
            in_valid = 1'b0;
        end
    endtask

    initial begin
        #5us;
        $fatal(1, "normalized to PG2L50H DDR3 write path timeout");
    end

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        allocate_frame(1'b1, 28'h000_0040);
        stage_frame_record(32'h1122_3344, 4'hf);
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!write_valid || write_ready || axi_awvalid || adapter_busy ||
                frame_alloc_ready)
                $fatal(1, "DDR init gating did not retain the frame record");
        end

        @(negedge clk);
        ddr_init_done = 1'b1;
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (adapter_busy || axi_awvalid || write_ready)
                $fatal(1, "Writer path bypassed the init synchronizer");
        end
        @(posedge clk);
        #1ns;
        if (!adapter_busy || !axi_awvalid || write_ready ||
            axi_awaddr !== 28'h000_0040 || axi_awlen !== 4'd0 ||
            axi_awuser_id !== 4'h2 || axi_awuser_ap ||
            axi_wdata !== {89'd0, 1'b0, 1'b1, 1'b1, 4'hf,
                           32'h1122_3344} || axi_wstrb !== 16'h001f ||
            !write_last || !write_frame_end || write_protocol_error)
            $fatal(1, "First normalized record did not reach canonical AW/W fields");

        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!write_valid || !axi_awvalid || write_ready || frame_alloc_ready ||
                axi_awaddr !== 28'h000_0040 ||
                axi_wdata !== {89'd0, 1'b0, 1'b1, 1'b1, 4'hf,
                               32'h1122_3344})
                $fatal(1, "Writer released or fields changed before AW acceptance");
        end

        @(negedge clk);
        axi_awready = 1'b1;
        @(posedge clk);
        #1ns;
        axi_awready = 1'b0;
        if (!write_valid || write_ready || axi_awvalid || !adapter_busy ||
            frame_alloc_ready || aw_count != 1)
            $fatal(1, "AW acceptance released the writer before data consumption");

        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!write_valid || write_ready || frame_alloc_ready ||
                axi_wdata !== {89'd0, 1'b0, 1'b1, 1'b1, 4'hf,
                               32'h1122_3344} || axi_wstrb !== 16'h001f)
                $fatal(1, "Writer or data changed while waiting for axi_wready");
        end

        @(negedge clk);
        axi_wready = 1'b1;
        #1ns;
        if (!write_ready)
            $fatal(1, "Data consumption was not propagated to writer ready");
        @(posedge clk);
        #1ns;
        axi_wready = 1'b0;
        if (write_valid || adapter_busy || !frame_alloc_ready ||
            write_complete_count != 1)
            $fatal(1, "Frame record did not release exactly on data consumption");

        allocate_frame(1'b0, 28'h000_0080);
        stage_frame_record(32'haabb_ccdd, 4'h3);
        @(posedge clk);
        #1ns;
        if (!axi_awvalid || axi_awaddr !== 28'h000_0080 ||
            axi_wdata !== {89'd0, 1'b0, 1'b1, 1'b1, 4'h3,
                           32'haabb_ccdd} || axi_wstrb !== 16'h0013)
            $fatal(1, "Second normalized record fields mismatch");
        @(negedge clk);
        axi_awready = 1'b1;
        axi_wready = 1'b1;
        #1ns;
        if (!write_ready)
            $fatal(1, "Same-cycle canonical acceptance did not complete writer");
        @(posedge clk);
        #1ns;
        axi_awready = 1'b0;
        axi_wready = 1'b0;
        if (write_valid || adapter_busy || !frame_alloc_ready ||
            aw_count != 2 || write_complete_count != 2)
            $fatal(1, "Second frame did not complete exactly once");

        $display("INFO: normalized slotted writer to PG2L50H DDR3 write path verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
