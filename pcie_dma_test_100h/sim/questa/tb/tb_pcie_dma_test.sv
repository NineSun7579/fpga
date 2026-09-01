`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_pcie_dma_test.sv
 * @brief Self-checking S2-A smoke test for the project-owned PCIe top level.
 *
 * The testbench verifies top-level elaboration, real reset debounce/synchronizer
 * behavior, LED reset ownership, and deterministic outputs around a controlled
 * PCIe boundary model. It does not verify a physical or protocol-level link.
 */

/**
 * @brief Exercise reset release and interruption through `pcie_dma_test`.
 *
 * The differential reference clock must run throughout reset release because
 * both project debounce instances use the derived `ref_clk`. Failure paths use
 * `$fatal`; the success path emits exactly one `TEST PASS` line.
 */
module tb_pcie_dma_test;

    localparam time REF_HALF_PERIOD = 5ns;
    localparam int unsigned RESET_RELEASE_MINIMUM = 49152;
    localparam int unsigned RESET_RELEASE_LIMIT = 60000;
    localparam int unsigned LINK_MODEL_LIMIT = 128;

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

    logic [22:0] ref_count_before_button_reset;
    logic [22:0] ref_count_before_link;
    logic [26:0] pclk_count_before_link;

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

    GTP_GRS GRS_INST (
        .GRS_N (1'b1)
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
                @(posedge ref_clk_p);
                if (dut.sync_button_rst_n &&
                    dut.sync_perst_n &&
                    dut.core_rst_n &&
                    dut.ref_core_rst_n &&
                    dut.s_pclk_rstn) begin
                    released = 1'b1;
                    break;
                end
            end
            if (!released) begin
                $fatal(1, "Reset release timeout");
            end
            if (cycle < RESET_RELEASE_MINIMUM) begin
                $fatal(1, "Reset debounce released earlier than the configured minimum");
            end
        end
    endtask

    task automatic wait_for_model_link;
        bit linked;
        int unsigned cycle;
        begin
            linked = 1'b0;
            for (cycle = 0; cycle < LINK_MODEL_LIMIT; cycle++) begin
                @(posedge ref_clk_p);
                if (dut.smlh_link_up && dut.rdlh_link_up) begin
                    linked = 1'b1;
                    break;
                end
            end
            if (!linked) begin
                $fatal(1, "Controlled PCIe model did not assert link indication");
            end
        end
    endtask

    // A bounded watchdog prevents a stalled reset or model from hanging CI.
    initial begin
        #3ms;
        $fatal(1, "Simulation timeout");
    end

    initial begin
        repeat (8) @(posedge ref_clk_p);
        if (ref_led !== 1'b1 || pclk_led !== 1'b1) begin
            $fatal(1, "LED reset values are not asserted");
        end

        button_rst_n = 1'b1;
        perst_n = 1'b1;
        wait_for_reset_release();
        @(negedge ref_clk_p);

        if (dut.smlh_link_up !== 1'b0 || dut.rdlh_link_up !== 1'b0) begin
            $fatal(1, "Model link indication asserted before the observation window");
        end
        if (dut.ref_led_cnt !== 23'b0 || dut.pclk_led_cnt !== 27'b0) begin
            $fatal(1, "LED counters advanced while link indication was low");
        end

        ref_count_before_link = dut.ref_led_cnt;
        pclk_count_before_link = dut.pclk_led_cnt;
        wait_for_model_link();
        repeat (8) @(posedge ref_clk_p);
        @(negedge ref_clk_p);

        if (dut.ref_led_cnt <= ref_count_before_link ||
            dut.pclk_led_cnt <= pclk_count_before_link) begin
            $fatal(1, "LED counters did not advance after model link indication");
        end
        if ($isunknown({txn, txp, ref_led, pclk_led})) begin
            $fatal(1, "Top-level observable output contains an unknown value");
        end

        // Button reset owns the PCIe core/pclk domain but does not directly
        // reset the ref-clock LED counter, whose reset is PERST#-derived.
        ref_count_before_button_reset = dut.ref_led_cnt;
        button_rst_n = 1'b0;
        wait (dut.sync_button_rst_n === 1'b0 && dut.core_rst_n === 1'b0);
        repeat (4) @(posedge ref_clk_p);
        if (pclk_led !== 1'b1 || dut.pclk_led_cnt !== 27'b0) begin
            $fatal(1, "Button reset did not reset the pclk LED domain");
        end
        if (dut.ref_led_cnt !== ref_count_before_button_reset) begin
            $fatal(1, "Button reset changed the ref LED counter");
        end
        repeat (8) @(posedge ref_clk_p);
        if (dut.ref_led_cnt !== ref_count_before_button_reset) begin
            $fatal(1, "Ref LED counter changed while model link indication was low");
        end

        button_rst_n = 1'b1;
        wait_for_reset_release();
        wait_for_model_link();

        perst_n = 1'b0;
        wait (dut.sync_perst_n === 1'b0 && dut.core_rst_n === 1'b0);
        repeat (4) @(posedge ref_clk_p);
        if (ref_led !== 1'b1 || pclk_led !== 1'b1 ||
            dut.ref_led_cnt !== 23'b0 || dut.pclk_led_cnt !== 27'b0) begin
            $fatal(1, "PERST# did not reset both LED domains");
        end

        // Release PERST# independently so its debounce latency cannot be hidden
        // by the button-reset debounce instance used during initial startup.
        perst_n = 1'b1;
        wait_for_reset_release();
        wait_for_model_link();

        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
