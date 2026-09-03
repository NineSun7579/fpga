`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_ddr3_read_adapter.sv
 * @brief Verify one canonical PG2L50H DDR3 read beat per normalized command.
 *
 * @details
 * The test models the canonical AR/R boundary, including its missing RREADY,
 * and checks initialization gating, AR backpressure, output buffering,
 * same-cycle AR/R return, metadata restoration, protocol faults, and reset.
 */
module tb_rgb565_pg2l50h_ddr3_read_adapter;
    logic         clk = 1'b0;
    logic         rst_n = 1'b0;
    logic         ddr_init_done = 1'b0;
    logic         in_valid = 1'b0;
    logic         in_ready;
    logic [27:0]  in_addr = 28'd0;
    logic [27:0]  axi_araddr;
    logic         axi_aruser_ap;
    logic [3:0]   axi_aruser_id;
    logic [3:0]   axi_arlen;
    logic         axi_arvalid;
    logic         axi_arready = 1'b0;
    logic [127:0] axi_rdata = 128'd0;
    logic [3:0]   axi_rid = 4'd0;
    logic         axi_rlast = 1'b0;
    logic         axi_rvalid = 1'b0;
    logic         out_valid;
    logic         out_ready = 1'b0;
    logic [31:0]  out_data;
    logic [3:0]   out_keep;
    logic         out_last;
    logic         out_frame_end;
    logic         out_protocol_error;
    logic         port_fault_pulse;
    logic         busy;

    integer ar_count = 0;
    integer out_count = 0;
    integer port_fault_count = 0;

    rgb565_pg2l50h_ddr3_read_adapter #(
        .REQUEST_ID(4'h6)
    ) dut (.*);

    always #5ns clk = ~clk;

    always @(posedge clk) begin
        if (axi_arvalid && axi_arready)
            ar_count = ar_count + 1;
        if (out_valid && out_ready)
            out_count = out_count + 1;
        #1ns;
        if (port_fault_pulse)
            port_fault_count = port_fault_count + 1;
    end

    initial begin
        #5us;
        $fatal(1, "PG2L50H DDR3 read adapter timeout");
    end

    initial begin
        repeat (2) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        in_valid = 1'b1;
        in_addr = 28'h012_3456;
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (busy || axi_arvalid || in_ready)
                $fatal(1, "Read adapter admitted a command before DDR init");
        end

        @(negedge clk);
        ddr_init_done = 1'b1;
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (busy || axi_arvalid || in_ready)
                $fatal(1, "Read adapter bypassed the init synchronizer");
        end
        @(posedge clk);
        #1ns;
        if (!busy || !axi_arvalid || in_ready || axi_araddr !== 28'h012_3456 ||
            axi_aruser_ap || axi_aruser_id !== 4'h6 || axi_arlen !== 4'd0)
            $fatal(1, "Read adapter did not capture the first command");

        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!axi_arvalid || in_ready || axi_araddr !== 28'h012_3456)
                $fatal(1, "AR fields changed under backpressure");
        end

        // AR acceptance does not depend on a response arriving in the same cycle.
        @(negedge clk);
        axi_arready = 1'b1;
        #1ns;
        if (!in_ready)
            $fatal(1, "Canonical AR handshake did not release the input command");
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        axi_arready = 1'b0;
        if (!busy || axi_arvalid || out_valid)
            $fatal(1, "Read adapter did not enter response wait state");

        // The unbackpressured canonical response must be buffered for the consumer.
        @(negedge clk);
        axi_rdata = {89'd0, 1'b0, 1'b1, 1'b1, 4'h3, 32'h1122_3344};
        axi_rid = 4'h6;
        axi_rlast = 1'b1;
        axi_rvalid = 1'b1;
        @(posedge clk);
        #1ns;
        axi_rvalid = 1'b0;
        axi_rdata = 128'd0;
        if (!out_valid || out_data !== 32'h1122_3344 || out_keep !== 4'h3 ||
            !out_last || !out_frame_end || out_protocol_error)
            $fatal(1, "Read response metadata was not restored correctly");
        repeat (2) begin
            @(posedge clk);
            #1ns;
            if (!out_valid || out_data !== 32'h1122_3344 || out_keep !== 4'h3 ||
                !out_last || !out_frame_end || out_protocol_error)
                $fatal(1, "Buffered read response changed under backpressure");
        end
        @(negedge clk);
        out_ready = 1'b1;
        @(posedge clk);
        #1ns;
        out_ready = 1'b0;
        if (busy || out_valid)
            $fatal(1, "Buffered read response did not complete exactly once");

        // AR and R may complete together; RID/RLAST mismatches must mark the record.
        @(negedge clk);
        in_addr = 28'h000_0040;
        in_valid = 1'b1;
        @(posedge clk);
        #1ns;
        if (!axi_arvalid)
            $fatal(1, "Second command did not enter AR state");
        @(negedge clk);
        axi_arready = 1'b1;
        axi_rdata = {89'd0, 1'b0, 1'b0, 1'b1, 4'hf, 32'ha5a5_5a5a};
        axi_rid = 4'h2;
        axi_rlast = 1'b0;
        axi_rvalid = 1'b1;
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        axi_arready = 1'b0;
        axi_rvalid = 1'b0;
        if (!out_valid || out_data !== 32'ha5a5_5a5a || out_keep !== 4'hf ||
            !out_last || out_frame_end || !out_protocol_error)
            $fatal(1, "Same-cycle AR/R or protocol-error handling failed");
        @(negedge clk);
        out_ready = 1'b1;
        @(posedge clk);
        #1ns;
        out_ready = 1'b0;

        // RVALID without an accepted command is a canonical port contract fault.
        @(negedge clk);
        axi_rvalid = 1'b1;
        axi_rlast = 1'b1;
        @(posedge clk);
        #1ns;
        axi_rvalid = 1'b0;
        if (!port_fault_pulse)
            $fatal(1, "Unsolicited RVALID did not raise one port fault");

        // Reset clears a pending AR command and the init synchronizer.
        @(negedge clk);
        in_valid = 1'b1;
        in_addr = 28'h000_0080;
        @(posedge clk);
        #1ns;
        if (!axi_arvalid)
            $fatal(1, "Reset scenario did not start an AR command");
        @(negedge clk);
        rst_n = 1'b0;
        #1ns;
        if (busy || axi_arvalid || out_valid || in_ready)
            $fatal(1, "Reset did not clear the read adapter");
        if (ar_count != 2 || out_count != 2 || port_fault_count != 1)
            $fatal(1, "Read adapter handshake counts mismatch");

        $display("INFO: PG2L50H DDR3 AR/R adapter and metadata restore verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
