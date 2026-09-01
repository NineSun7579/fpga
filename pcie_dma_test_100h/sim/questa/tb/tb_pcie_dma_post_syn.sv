`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_pcie_dma_post_syn.sv
 * @brief Self-checking post-synthesis reset-path smoke for the PCIe top level.
 *
 * The testbench verifies that the PDS synthesis netlist elaborates with USIM,
 * releases its debounced resets, and preserves the reference-clock LED counter
 * response to the synthesized link observation nets. It does not verify a
 * PCIe link, DMA traffic, place-and-route behavior, or timing.
 */

/**
 * @brief Exercise reset ownership and a preserved reference-clock data path.
 *
 * Assumption: PDS preserves the named top-level reset, link, and LED-counter
 * nets in the generated synthesis artifact. The static gate rejects a missing
 * artifact or contract drift; runtime failures use `$fatal`.
 *
 * Hazard: forcing synthesized link nets bypasses the PCIe protocol model. The
 * result is only a structural post-synthesis smoke and must not be used as link
 * or DMA evidence.
 */
module tb_pcie_dma_post_syn;

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

    logic [22:0] ref_count_before_link;
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
                if (dut.sync_button_rst_n === 1'b1 &&
                    dut.sync_perst_n === 1'b1) begin
                    released = 1'b1;
                    break;
                end
            end
            if (!released) begin
                $fatal(1, "Post-synthesis reset release timeout");
            end
        end
    endtask

    // A bounded watchdog prevents a stalled primitive or reset path from
    // hanging local automation or CI.
    initial begin
        #2ms;
        $fatal(1, "Post-synthesis simulation timeout");
    end

    initial begin
        repeat (8) @(posedge ref_clk_p);
        if (ref_led !== 1'b1 || pclk_led !== 1'b1) begin
            $fatal(1, "Post-synthesis LED reset values are not asserted");
        end

        button_rst_n = 1'b1;
        perst_n = 1'b1;
        wait_for_reset_release();
        @(negedge ref_clk_p);

        if ($isunknown({ref_led, pclk_led, dut.ref_led_cnt})) begin
            $fatal(1, "Post-synthesis reset observation contains an unknown value");
        end

        ref_count_before_link = dut.ref_led_cnt;
        force dut.smlh_link_up = 1'b1;
        force dut.rdlh_link_up = 1'b1;
        repeat (16) @(posedge ref_clk_p);
        @(negedge ref_clk_p);
        if (dut.ref_led_cnt <= ref_count_before_link) begin
            $fatal(1, "Post-synthesis reference counter did not advance");
        end

        release dut.smlh_link_up;
        release dut.rdlh_link_up;
        ref_count_before_button_reset = dut.ref_led_cnt;
        button_rst_n = 1'b0;
        wait (dut.sync_button_rst_n === 1'b0);
        repeat (8) @(posedge ref_clk_p);
        if (dut.ref_led_cnt !== ref_count_before_button_reset) begin
            $fatal(1, "Button reset changed the PERST-owned reference counter");
        end

        perst_n = 1'b0;
        wait (dut.sync_perst_n === 1'b0);
        repeat (4) @(posedge ref_clk_p);
        if (dut.ref_led_cnt !== 23'b0 || ref_led !== 1'b1) begin
            $fatal(1, "PERST did not reset the post-synthesis reference path");
        end

        $display("INFO: POST_SYN_RESET_PATH_OK");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
