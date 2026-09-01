`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_pcie_dma_post_pnr_func.sv
 * @brief Self-checking post-PNR functional smoke for the PCIe top level.
 *
 * The testbench verifies that the PDS placed-and-routed netlist elaborates
 * with VSIM, releases the project reset paths, and preserves the reference-
 * clock LED counter behavior. It does not verify a PCIe link, DMA traffic,
 * SDF annotation, or timing.
 *
 * @par Clock and reset contract
 * The differential reference clock runs continuously at 100 MHz. Active-low
 * button and PERST inputs are asserted asynchronously by the testbench; PASS
 * requires the implemented debounce/synchronizer paths to release in the
 * reference-clock domain within the bounded wait.
 */

/**
 * @brief Exercise reset ownership and a preserved post-PNR data path.
 *
 * Assumption: PDS preserves the named reset, link-observation, and LED-counter
 * nets in the functional netlist. The static gate rejects contract drift, and
 * runtime failures use `$fatal`.
 *
 * Hazard: forcing the link-observation nets bypasses the PCIe protocol and
 * hard-IP models. This result is only a post-PNR structural/functional smoke;
 * it is not link, DMA, SDF, or timing evidence.
 *
 * @par Failure contract
 * Unknown observations, reset/counter mismatches, and watchdog expiry call
 * `$fatal`; success emits exactly one `TEST PASS` before `$finish`.
 */
module tb_pcie_dma_post_pnr_func;

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
                $fatal(1, "Post-PNR functional reset release timeout");
            end
        end
    endtask

    // A bounded watchdog prevents a primitive or reset-path failure from
    // hanging local automation or CI.
    initial begin
        #2ms;
        $fatal(1, "Post-PNR functional simulation timeout");
    end

    initial begin
        repeat (8) @(posedge ref_clk_p);
        if (ref_led !== 1'b1 || pclk_led !== 1'b1) begin
            $fatal(1, "Post-PNR functional LED reset values are not asserted");
        end

        button_rst_n = 1'b1;
        perst_n = 1'b1;
        wait_for_reset_release();
        @(negedge ref_clk_p);

        if ($isunknown({ref_led, pclk_led, dut.ref_led_cnt})) begin
            $fatal(1, "Post-PNR functional reset observation contains an unknown value");
        end

        ref_count_before_link = dut.ref_led_cnt;
        force dut.smlh_link_up = 1'b1;
        force dut.rdlh_link_up = 1'b1;
        repeat (16) @(posedge ref_clk_p);
        @(negedge ref_clk_p);
        if (dut.ref_led_cnt <= ref_count_before_link) begin
            $fatal(1, "Post-PNR functional reference counter did not advance");
        end

        release dut.smlh_link_up;
        release dut.rdlh_link_up;
        ref_count_before_button_reset = dut.ref_led_cnt;
        button_rst_n = 1'b0;
        wait (dut.sync_button_rst_n === 1'b0);
        repeat (8) @(posedge ref_clk_p);
        if (dut.ref_led_cnt !== ref_count_before_button_reset) begin
            $fatal(1, "Button reset changed the PERST-owned post-PNR counter");
        end

        perst_n = 1'b0;
        wait (dut.sync_perst_n === 1'b0);
        repeat (4) @(posedge ref_clk_p);
        if (dut.ref_led_cnt !== 23'b0 || ref_led !== 1'b1) begin
            $fatal(1, "PERST did not reset the post-PNR reference path");
        end

        $display("INFO: POST_PNR_FUNC_RESET_PATH_OK");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
