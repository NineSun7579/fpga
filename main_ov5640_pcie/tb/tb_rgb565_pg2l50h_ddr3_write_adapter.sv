`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_ddr3_write_adapter.sv
 * @brief Verify one normalized write record against the PG2L50H DDR3 user port.
 *
 * @details
 * The test models only the canonical application-side AW and `axi_wready`
 * handshake. It does not model DDR3 calibration, storage, reads, PHY timing,
 * or physical address decoding.
 */
module tb_rgb565_pg2l50h_ddr3_write_adapter;
    logic         clk = 1'b0;
    logic         rst_n = 1'b0;
    logic         ddr_init_done = 1'b0;
    logic         in_valid = 1'b0;
    logic         in_ready;
    logic [27:0]  in_addr = 28'd0;
    logic [127:0] in_data = 128'd0;
    logic [15:0]  in_strb = 16'd0;

    logic [27:0]  axi_awaddr;
    logic         axi_awuser_ap;
    logic [3:0]   axi_awuser_id;
    logic [3:0]   axi_awlen;
    logic         axi_awvalid;
    logic         axi_awready = 1'b0;
    logic [127:0] axi_wdata;
    logic [15:0]  axi_wstrb;
    logic         axi_wready = 1'b0;
    logic         busy;

    integer aw_count = 0;
    integer w_count = 0;
    integer upstream_count = 0;

    rgb565_pg2l50h_ddr3_write_adapter #(
        .REQUEST_ID(4'h5)
    ) dut (.*);

    always #5ns clk = ~clk;

    always @(posedge clk) begin
        if (axi_awvalid && axi_awready)
            aw_count = aw_count + 1;
        if (busy && axi_wready &&
            ((axi_awvalid && axi_awready) || !axi_awvalid))
            w_count = w_count + 1;
        if (in_valid && in_ready)
            upstream_count = upstream_count + 1;
    end

    initial begin
        #5us;
        $fatal(1, "PG2L50H DDR3 write adapter timeout");
    end

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        // Init gating: a held source request must not start before calibration.
        in_addr = 28'h012_3456;
        in_data = 128'h0011_2233_4455_6677_8899_aabb_ccdd_eeff;
        in_strb = 16'h0ff0;
        in_valid = 1'b1;
        axi_wready = 1'b1;
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (in_ready || axi_awvalid || busy)
                $fatal(1, "Adapter accepted a request before DDR init");
        end

        // Capture after init, then hold AW and data while address is blocked.
        @(negedge clk);
        ddr_init_done = 1'b1;
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (in_ready || axi_awvalid || busy)
                $fatal(1, "Adapter bypassed the init synchronizer");
        end
        @(posedge clk);
        #1ns;
        if (!busy || !axi_awvalid || in_ready || axi_awaddr !== 28'h012_3456 ||
            axi_awuser_ap || axi_awuser_id !== 4'h5 || axi_awlen !== 4'd0 ||
            axi_wdata !== in_data || axi_wstrb !== 16'h0ff0)
            $fatal(1, "Adapter did not capture the first write record");

        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!axi_awvalid || in_ready || axi_awaddr !== 28'h012_3456 ||
                axi_wdata !== 128'h0011_2233_4455_6677_8899_aabb_ccdd_eeff ||
                axi_wstrb !== 16'h0ff0)
                $fatal(1, "AW or write data changed under address backpressure");
        end

        // AW acceptance alone must not release the normalized source record.
        @(negedge clk);
        axi_awready = 1'b1;
        axi_wready = 1'b0;
        @(posedge clk);
        #1ns;
        axi_awready = 1'b0;
        if (!busy || axi_awvalid || in_ready || aw_count != 1 ||
            axi_wdata !== 128'h0011_2233_4455_6677_8899_aabb_ccdd_eeff ||
            axi_wstrb !== 16'h0ff0)
            $fatal(1, "AW handshake incorrectly completed the write record");

        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!busy || in_ready || axi_wdata !==
                128'h0011_2233_4455_6677_8899_aabb_ccdd_eeff)
                $fatal(1, "Write data changed while waiting for axi_wready");
        end

        // One data-consume edge is also the upstream completion handshake.
        @(negedge clk);
        axi_wready = 1'b1;
        #1ns;
        if (!in_ready)
            $fatal(1, "Adapter did not expose completion ready with axi_wready");
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        axi_wready = 1'b0;
        if (busy || axi_awvalid || aw_count != 1 || w_count != 1 ||
            upstream_count != 1)
            $fatal(1, "First write did not complete exactly once");

        // The canonical port may accept AW and its single data beat together.
        @(negedge clk);
        in_addr = 28'h000_0040;
        in_data = 128'hfedc_ba98_7654_3210_0123_4567_89ab_cdef;
        in_strb = 16'hffff;
        in_valid = 1'b1;
        @(posedge clk);
        #1ns;
        if (!axi_awvalid || !busy)
            $fatal(1, "Second write did not enter AW state");
        @(negedge clk);
        axi_awready = 1'b1;
        axi_wready = 1'b1;
        #1ns;
        if (!in_ready)
            $fatal(1, "Same-cycle AW/W acceptance did not assert upstream ready");
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        axi_awready = 1'b0;
        axi_wready = 1'b0;
        if (busy || aw_count != 2 || w_count != 2 || upstream_count != 2)
            $fatal(1, "Same-cycle AW/W write did not complete exactly once");

        // Asynchronous reset must cancel both AW-pending and W-pending states.
        @(negedge clk);
        in_valid = 1'b1;
        in_addr = 28'h000_0080;
        @(posedge clk);
        #1ns;
        if (!axi_awvalid)
            $fatal(1, "Reset-AW scenario did not start");
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (busy || axi_awvalid || in_ready)
            $fatal(1, "Reset did not clear AW-pending state");
        in_valid = 1'b0;
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);

        @(negedge clk);
        in_valid = 1'b1;
        in_addr = 28'h000_00c0;
        @(posedge clk);
        #1ns;
        @(negedge clk);
        axi_awready = 1'b1;
        @(posedge clk);
        #1ns;
        axi_awready = 1'b0;
        if (!busy || axi_awvalid)
            $fatal(1, "Reset-W scenario did not reach data state");
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (busy || axi_awvalid || in_ready)
            $fatal(1, "Reset did not clear W-pending state");

        $display("INFO: PG2L50H DDR3 AW-to-W write adapter protocol verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
