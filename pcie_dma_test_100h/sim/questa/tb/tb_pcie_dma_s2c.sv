`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_pcie_dma_s2c.sv
 * @brief Self-checking S2-C fixed DMA write/readback over the real PCIe link.
 *
 * @details
 * The generated `pango_pcie_top_sim` Root Complex writes one fixed DWORD to
 * the project-owned `pcie_dma_test` Endpoint BAR0, then reads the same address.
 * The test compares the Endpoint write payload and the complete 32-bit data
 * returned through the Root Complex completion path. It does not prove the
 * RK3568 Root Complex, board electrical behavior, negotiated width/rate,
 * sustained DMA performance, error recovery, or post-implementation timing.
 *
 * @par Clock and reset
 * - Clock: shared 100 MHz differential reference clock.
 * - Reset: button reset releases first; PERST# releases ten refclk cycles later.
 *
 * @warning
 * The project top does not expose link, LTSSM, UART APB, or DMA observation
 * ports. This simulation therefore depends on named internal status and DMA
 * nets. Any top-level or generated-IP hierarchy change requires review of this
 * test and its static gate.
 */
module tb_pcie_dma_s2c;

    localparam time REF_HALF_PERIOD = 5ns;
    localparam int unsigned LINK_TIMEOUT_CYCLES = 500_000;
    localparam int unsigned LINK_STABLE_CYCLES = 32;
    localparam int unsigned DMA_TIMEOUT_CYCLES = 50_000;
    localparam logic [4:0] LTSSM_L0 = 5'h11;

    // The controller encodes length as DWORD count minus one.
    localparam logic [9:0] DMA_LENGTH_MINUS_ONE = 10'h000;
    localparam logic [31:0] DMA_ADDRESS = 32'h0000_2000;
    localparam logic [31:0] DMA_DATA = 32'hA5C3_5A3C;

    logic button_rst_n = 1'b0;
    logic perst_n = 1'b0;
    logic ref_clk_p = 1'b0;
    logic capture_endpoint_write = 1'b0;
    logic capture_read_completion = 1'b0;
    logic endpoint_write_seen;
    logic read_completion_seen;
    logic [31:0] written_data;
    logic [31:0] readback_data;
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

    // Intent: capture the complete Endpoint BAR0 write payload before the
    // subsequent read can hide a missed or corrupted write transaction.
    always_ff @(posedge u_dut.pclk_div2 or negedge button_rst_n) begin
        if (!button_rst_n || !capture_endpoint_write) begin
            endpoint_write_seen <= 1'b0;
            written_data        <= 32'b0;
        end else if (u_dut.u_ips2l_pcie_dma.u_ips2l_pcie_dma_rx_top.bar0_wr_en) begin
            endpoint_write_seen <= 1'b1;
            written_data <=
                u_dut.u_ips2l_pcie_dma.u_ips2l_pcie_dma_rx_top.bar0_wr_data[31:0];
        end
    end

    // Intent: sample the endian-corrected payload used by the real completion
    // writer, rather than inspecting the RAM model through a private memory API.
    always_ff @(posedge u_rc.pclk_div2 or negedge button_rst_n) begin
        if (!button_rst_n || !capture_read_completion) begin
            read_completion_seen <= 1'b0;
            readback_data        <= 32'b0;
        end else if (
            u_rc.u_ips2l_pcie_dma.u_ips2l_pcie_dma_rx_top.
                u_ips2l_pcie_dma_tlp_rcv.cpld_data_valid
        ) begin
            read_completion_seen <= 1'b1;
            readback_data <=
                u_rc.u_ips2l_pcie_dma.u_ips2l_pcie_dma_rx_top.
                    u_ips2l_pcie_dma_tlp_rcv.axis_rx_data[31:0];
        end
    end

    // Intent: accept the final stable L0 window after any legal retraining.
    // Invariant: only consecutive all-link/all-L0 samples count as ready.
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
                $fatal(1, "S2-C link timeout before DMA");
            end
        end
    endtask

    // Assumption: the vendor RC UART-to-APB bridge remains present at the
    // hierarchy used by the generated example. The global watchdog bounds a
    // missing APB ready transition.
    task automatic rc_apb_write(
        input logic [15:0] address,
        input logic [31:0] data,
        input logic [3:0] strobe
    );
        begin
            @(posedge u_rc.ref_clk);
            #1ns;
            force u_rc.uart_p_addr  = address;
            force u_rc.uart_p_sel   = 1'b1;
            force u_rc.uart_p_strb  = strobe;
            force u_rc.uart_p_ce    = 1'b0;
            force u_rc.uart_p_we    = 1'b1;
            force u_rc.uart_p_wdata = data;

            @(posedge u_rc.ref_clk);
            #1ns;
            force u_rc.uart_p_ce = 1'b1;
            @(negedge u_rc.uart_p_rdy);
            #1ns;
            force u_rc.uart_p_addr  = 16'b0;
            force u_rc.uart_p_sel   = 1'b0;
            force u_rc.uart_p_strb  = 4'b0;
            force u_rc.uart_p_ce    = 1'b0;
            force u_rc.uart_p_we    = 1'b0;
            force u_rc.uart_p_wdata = 32'b0;
        end
    endtask

    task automatic pulse_cfg_tx;
        begin
            rc_apb_write(16'h9000, 32'h0100_0000, 4'b1000);
            rc_apb_write(16'h9000, 32'h0000_0000, 4'b1000);
            #1us;
        end
    endtask

    // Intent: configure only the BAR and command-register facts required by
    // this one-address test; no broad enumeration behavior is claimed.
    task automatic configure_endpoint_bar0;
        begin
            rc_apb_write(16'h9008, 32'h0100_0000, 4'b1000);
            rc_apb_write(16'h9000, 32'h0000_003D, 4'b0001);
            rc_apb_write(16'h9004, 32'h0100_0000, 4'b1000);

            rc_apb_write(16'h9008, 32'h0000_0004, 4'b0001);
            rc_apb_write(16'h9000, 32'h0000_0000, 4'b0010);
            rc_apb_write(16'h900C, DMA_ADDRESS, 4'b1111);
            pulse_cfg_tx();

            rc_apb_write(16'h9008, 32'h0000_0001, 4'b0001);
            rc_apb_write(16'h9000, 32'h0000_0600, 4'b0010);
            rc_apb_write(16'h900C, 32'h0000_0007, 4'b0001);
            pulse_cfg_tx();

            rc_apb_write(16'h7004, 32'h0000_0007, 4'b0001);
            rc_apb_write(16'h9008, 32'h0000_0000, 4'b1000);
            #2us;
        end
    endtask

    task automatic rc_dma_write_one_dw;
        begin
            // bit24=MWR, bit8=user data, bit16=32-bit address.
            rc_apb_write(16'h8140, 32'h0100_0100, 4'b1111);
            rc_apb_write(16'h8150, {22'b0, DMA_LENGTH_MINUS_ONE}, 4'b1111);
            rc_apb_write(16'h8160, DMA_ADDRESS, 4'b1111);
            rc_apb_write(16'h8180, DMA_DATA, 4'b1111);
        end
    endtask

    task automatic rc_dma_read_one_dw;
        begin
            // bit24=MRD, bit16=32-bit address.
            rc_apb_write(16'h8140, 32'h0000_0000, 4'b1111);
            rc_apb_write(16'h8150, {22'b0, DMA_LENGTH_MINUS_ONE}, 4'b1111);
            rc_apb_write(16'h8160, DMA_ADDRESS, 4'b1111);
        end
    endtask

    task automatic wait_for_endpoint_write;
        bit completed;
        int unsigned cycle;
        begin
            completed = 1'b0;
            for (cycle = 0; cycle < DMA_TIMEOUT_CYCLES; cycle++) begin
                @(posedge ref_clk_p);
                if (endpoint_write_seen === 1'b1) begin
                    completed = 1'b1;
                    break;
                end
            end
            if (!completed) begin
                $fatal(1, "Endpoint did not receive the fixed DMA write");
            end
        end
    endtask

    task automatic wait_for_read_completion;
        bit completed;
        int unsigned cycle;
        begin
            completed = 1'b0;
            for (cycle = 0; cycle < DMA_TIMEOUT_CYCLES; cycle++) begin
                @(posedge ref_clk_p);
                if (read_completion_seen === 1'b1) begin
                    completed = 1'b1;
                    break;
                end
            end
            if (!completed) begin
                $fatal(1, "Root Complex did not receive the DMA read completion");
            end
        end
    endtask

    // A bounded watchdog prevents APB, LTSSM, TLP, or completion stalls from
    // hanging an automated run.
    initial begin
        #8ms;
        $fatal(1, "PCIe S2-C simulation timeout");
    end

    initial begin
        force u_dut.rxd = 1'b1;
        force u_rc.uart_p_addr  = 16'b0;
        force u_rc.uart_p_sel   = 1'b0;
        force u_rc.uart_p_strb  = 4'b0;
        force u_rc.uart_p_ce    = 1'b0;
        force u_rc.uart_p_we    = 1'b0;
        force u_rc.uart_p_wdata = 32'b0;

        #100ns;
        button_rst_n = 1'b1;
        repeat (10) @(posedge ref_clk_p);
        perst_n = 1'b1;

        wait_for_real_link();
        configure_endpoint_bar0();

        capture_endpoint_write = 1'b1;
        repeat (2) @(posedge ref_clk_p);
        rc_dma_write_one_dw();
        wait_for_endpoint_write();
        if (written_data !== DMA_DATA) begin
            $fatal(1, "DMA write mismatch: expected=%08h actual=%08h",
                DMA_DATA, written_data);
        end

        capture_read_completion = 1'b1;
        repeat (2) @(posedge ref_clk_p);
        rc_dma_read_one_dw();
        wait_for_read_completion();
        if (readback_data !== DMA_DATA) begin
            $fatal(1, "DMA readback mismatch: expected=%08h actual=%08h",
                DMA_DATA, readback_data);
        end

        if ($isunknown({rc_txn, rc_txp, ep_txn, ep_txp})) begin
            $fatal(1, "PCIe lane output contains an unknown value after DMA");
        end

        $display("INFO: S2C_DMA_WRITE_READBACK_OK");
        $display("TEST PASS");
        $finish;
    end

endmodule

`default_nettype wire
