`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_pcie_dma_link.sv
 * @brief Self-checking S2-B link smoke for the project PCIe Endpoint.
 *
 * @details
 * The generated `pango_pcie_top_sim` acts as a simulation-only Root Complex,
 * while the project-owned `pcie_dma_test` remains the real Endpoint. The test
 * checks both link layers and both LTSSM instances reach L0 and remain stable.
 * It does not verify DMA data, negotiated width/rate, the RK3568 Root Complex,
 * or board-level lane, reference-clock, reset, and electrical behavior.
 *
 * @par Clock and reset
 * - Clock: shared 100 MHz differential reference clock.
 * - Reset: button reset releases first; PERST# releases ten refclk cycles later.
 *
 * @warning
 * The project top does not expose Endpoint link/LTSSM or UART pins. This test
 * therefore depends on named internal status nets and forces the hidden UART RX
 * line idle. Any top-level interface decision requires this test to be reviewed.
 */
module tb_pcie_dma_link;

    localparam time REF_HALF_PERIOD = 5ns;
    localparam int unsigned LINK_TIMEOUT_CYCLES = 500_000;
    localparam int unsigned LINK_STABLE_CYCLES = 32;
    localparam logic [4:0] LTSSM_L0 = 5'h11;

    logic button_rst_n = 1'b0;
    logic perst_n = 1'b0;
    logic ref_clk_p = 1'b0;
    wire ref_clk_n;

    wire [1:0] rc_txn;
    wire [1:0] rc_txp;
    wire [1:0] ep_txn;
    wire [1:0] ep_txp;
    wire rc_smlh_link_up;
    wire rc_rdlh_link_up;
    wire rc_txd;
    wire rc_ref_led;
    wire rc_pclk_led;
    wire ep_ref_led;
    wire ep_pclk_led;

    assign ref_clk_n = ~ref_clk_p;

    pango_pcie_top_sim #(
        .APP_DEV_NUM (0),
        .APP_BUS_NUM (0)
    ) u_rc (
        .button_rst_n (button_rst_n),
        .perst_n      (perst_n),
        .txd          (rc_txd),
        .rxd          (1'b1),
        .ref_clk_n    (ref_clk_n),
        .ref_clk_p    (ref_clk_p),
        .rxn          (ep_txn),
        .rxp          (ep_txp),
        .txn          (rc_txn),
        .txp          (rc_txp),
        .ref_led      (rc_ref_led),
        .pclk_led     (rc_pclk_led),
        .smlh_link_up (rc_smlh_link_up),
        .rdlh_link_up (rc_rdlh_link_up)
    );

    pcie_dma_test u_dut (
        .button_rst_n (button_rst_n),
        .ref_clk_p    (ref_clk_p),
        .ref_clk_n    (ref_clk_n),
        .perst_n      (perst_n),
        .rxn          (rc_txn),
        .rxp          (rc_txp),
        .txn          (ep_txn),
        .txp          (ep_txp),
        .ref_led      (ep_ref_led),
        .pclk_led     (ep_pclk_led)
    );

    // Pango RAM models resolve global reset through GRS_INST.GRSNET.
    GTP_GRS GRS_INST (
        .GRS_N (1'b1)
    );

    always #REF_HALF_PERIOD begin
        ref_clk_p = ~ref_clk_p;
    end

    // Intent: accept the final stable L0 window after any legal retraining.
    // Invariant: only consecutive all-link/all-L0 samples count toward PASS.
    task automatic wait_for_real_link;
        bit linked;
        int unsigned cycle;
        int unsigned stable_cycles;
        begin
            linked        = 1'b0;
            stable_cycles = 0;
            for (cycle = 0; cycle < LINK_TIMEOUT_CYCLES; cycle++) begin
                @(posedge ref_clk_p);
                if (rc_smlh_link_up === 1'b1 &&
                    rc_rdlh_link_up === 1'b1 &&
                    u_dut.smlh_link_up === 1'b1 &&
                    u_dut.rdlh_link_up === 1'b1 &&
                    u_rc.smlh_ltssm_state === LTSSM_L0 &&
                    u_dut.smlh_ltssm_state === LTSSM_L0) begin
                    stable_cycles = stable_cycles + 1;
                    if (stable_cycles == LINK_STABLE_CYCLES) begin
                        linked = 1'b1;
                        break;
                    end
                end else begin
                    stable_cycles = 0;
                end
            end

            if (!linked) begin
                $fatal(1,
                    "Real link timeout: rc=%b/%b/%h ep=%b/%b/%h rc_rst=%b ep_rst=%b",
                    rc_smlh_link_up,
                    rc_rdlh_link_up,
                    u_rc.smlh_ltssm_state,
                    u_dut.smlh_link_up,
                    u_dut.rdlh_link_up,
                    u_dut.smlh_ltssm_state,
                    u_rc.core_rst_n,
                    u_dut.core_rst_n);
            end
        end
    endtask

    // A bounded watchdog prevents vendor-model or LTSSM stalls from hanging CI.
    initial begin
        #6ms;
        $fatal(1, "PCIe S2-B simulation timeout");
    end

    initial begin
        // H2-B1 still owns the hardware UART decision. Holding the hidden RX
        // idle here prevents an undriven simulation net from perturbing APB.
        force u_dut.rxd = 1'b1;

        #100ns;
        button_rst_n = 1'b1;
        repeat (10) @(posedge ref_clk_p);
        perst_n = 1'b1;

        wait_for_real_link();

        if ($isunknown({rc_txn, rc_txp, ep_txn, ep_txp,
                        rc_ref_led, rc_pclk_led, ep_ref_led, ep_pclk_led})) begin
            $fatal(1, "Observable link or LED output contains an unknown value");
        end

        $display("INFO: S2B_REAL_LINK_UP");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
