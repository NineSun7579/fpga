`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_pcie_dma_post_pnr_timing.sv
 * @brief Self-checking post-PNR timing smoke for the PCIe top level.
 *
 * The testbench verifies that the PDS timing netlist elaborates with its
 * slow-corner SDF, releases the project reset paths, and preserves the
 * reference-clock LED counter behavior. It does not verify a PCIe link, DMA
 * traffic, H2-B1 closure, hardware operation, or release readiness.
 *
 * @par Clock and reset contract
 * The differential reference clock runs continuously at 100 MHz. Active-low
 * button and PERST inputs assert asynchronously. Their release is driven on a
 * falling reference-clock edge so the next rising edge has 5 ns of margin;
 * tool timing checks remain the sign-off source for recovery and removal.
 */

/**
 * @brief Exercise SDF-annotated reset ownership and a preserved data path.
 *
 * Assumption: the PDS timing netlist is elaborated from the directory that
 * contains `pcie_dma_test_sta.sdf`, and the static/runtime gates reject a
 * missing or mismatched SDF before accepting this test.
 *
 * Hazard: this smoke deliberately does not force any mapped design signal.
 * Without a Root Complex the link-qualified counter enable should remain
 * inactive; the test therefore checks reset ownership and idle stability,
 * not PCIe protocol activity or an enabled counter transition.
 *
 * @par Failure contract
 * Unknown observations, reset/counter mismatches, watchdog expiry, SDF
 * errors, instance mismatches, and unapproved timing violations fail the
 * launcher; success emits exactly one `TEST PASS` before `$finish`.
 */
module tb_pcie_dma_post_pnr_timing;

    localparam time REF_HALF_PERIOD = 5ns;
    localparam int unsigned RESET_RELEASE_LIMIT = 60000;

    logic button_rst_n = 1'b0;
    logic ref_clk_p = 1'b0;
    logic ref_clk_n = 1'b1;
    logic perst_n = 1'b0;
    logic [1:0] rxn = 2'b11;
    logic [1:0] rxp = 2'b00;

    wire [1:0] txn;
    wire [1:0] txp;
    wire ref_led;
    wire pclk_led;

    logic [22:0] ref_count_before_idle;
    logic [22:0] ref_count_before_button_reset;

    pcie_dma_test dut (
        .button_rst_n (button_rst_n),
        .ref_clk_p    (ref_clk_p),
        .ref_clk_n    (ref_clk_n),
        .perst_n      (perst_n),
        .rxn          (rxn),
        .rxp          (rxp),
        .txn          (txn),
        .txp          (txp),
        .ref_led      (ref_led),
        .pclk_led     (pclk_led)
    );

    always #REF_HALF_PERIOD begin
        ref_clk_p = ~ref_clk_p;
        ref_clk_n = ~ref_clk_n;
    end

    task automatic wait_for_reset_release;
        bit released;
        int unsigned cycle;
        begin
            released = 1'b0;
            for (cycle = 0; cycle < RESET_RELEASE_LIMIT; cycle++) begin
                @(negedge ref_clk_p);
                if (dut.sync_button_rst_n === 1'b1 &&
                    dut.sync_perst_n === 1'b1) begin
                    released = 1'b1;
                    break;
                end
            end
            if (!released) begin
                $fatal(1, "Post-PNR timing reset release timeout");
            end
        end
    endtask

    // A bounded watchdog prevents timing-model or reset-path failures from
    // hanging local automation or CI.
    initial begin
        #2ms;
        $fatal(1, "Post-PNR timing simulation timeout");
    end

    initial begin
        repeat (8) @(posedge ref_clk_p);
        @(negedge ref_clk_p);
        if (ref_led !== 1'b1 || pclk_led !== 1'b1) begin
            $fatal(1, "Post-PNR timing LED reset values are not asserted");
        end

        // Release both asynchronous inputs away from the active clock edge.
        button_rst_n = 1'b1;
        perst_n = 1'b1;
        wait_for_reset_release();
        $display("INFO: POST_PNR_TIMING_RESET_RELEASED time=%0t", $time);

        // Keep the no-force observation window open while the mapped HSST
        // reset debounce state changes naturally.
        repeat (80) @(posedge ref_clk_p);
        @(negedge ref_clk_p);

        if ($isunknown({ref_led, pclk_led, dut.ref_led_cnt})) begin
            $fatal(1, "Post-PNR timing reset observation contains an unknown value");
        end

        ref_count_before_idle = dut.ref_led_cnt;
        repeat (8) @(posedge ref_clk_p);
        @(negedge ref_clk_p);
        if (dut.ref_led_cnt !== ref_count_before_idle) begin
            $fatal(1, "Post-PNR timing reference counter changed without link enable");
        end

        ref_count_before_button_reset = dut.ref_led_cnt;
        button_rst_n = 1'b0;
        wait (dut.sync_button_rst_n === 1'b0);
        repeat (8) @(posedge ref_clk_p);
        @(negedge ref_clk_p);
        if (dut.ref_led_cnt !== ref_count_before_button_reset) begin
            $fatal(1, "Button reset changed the PERST-owned post-PNR timing counter");
        end

        perst_n = 1'b0;
        wait (dut.sync_perst_n === 1'b0);
        repeat (4) @(posedge ref_clk_p);
        @(negedge ref_clk_p);
        if (dut.ref_led_cnt !== 23'b0 || ref_led !== 1'b1) begin
            $fatal(1, "PERST did not reset the post-PNR timing reference path");
        end

        $display("INFO: POST_PNR_TIMING_RESET_PATH_OK");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
