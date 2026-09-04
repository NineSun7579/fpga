`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv
 * @brief Verify the single-outstanding DDR-to-PCIe MWR32 asynchronous mailbox.
 *
 * @details
 * The expected DUT uses a synchronized request toggle plus bundled-data
 * multi-cycle-path transfer. Source payload is captured when a request is
 * accepted and must remain in source-domain holding registers until the
 * returned completion token is observed. The destination detects the
 * synchronized token, waits one destination cycle before sampling the stable
 * bundle, and then holds its registered request and payload through the real
 * downstream ACK edge. The test deliberately changes upstream payload after
 * source capture to prove that the CDC bundle comes from those holding
 * registers rather than from live upstream pins.
 *
 * This test does not claim to model metastability or physical bus skew. Static
 * timing constraints must bound the source holding-register to destination
 * capture-register paths; the payload bus must not be hidden by a blanket
 * false-path exception. The two-stage control synchronizers and their vendor
 * attributes remain CDC-tool and implementation-signoff responsibilities.
 *
 * Reset contract: active-low resets may assert asynchronously and release only
 * while their local clocks run. An idle single-domain reset is recoverable
 * after both channel-ready outputs return. A reset during an outstanding
 * transaction is not exactly-once recoverable: the surviving domain must emit
 * one local fault pulse, latch the corresponding sticky fault, suppress silent
 * completion and automatic replay, and require a coordinated two-domain reset
 * before accepting more traffic. Each sticky fault is cleared only by its own
 * local reset.
 */
module tb_rgb565_pg2l50h_pcie_mwr32_async_mailbox;
    logic src_fast_done;
    logic dst_fast_done;

    // The periods are intentionally non-harmonic and the destination clocks
    // start with non-zero phase offsets to exercise unrelated sampling edges.
    rgb565_pg2l50h_pcie_mwr32_async_mailbox_case #(
        .CASE_ID(0),
        .SRC_HALF_PERIOD(4ns),
        .DST_HALF_PERIOD(7ns),
        .DST_START_PHASE(2ns),
        .RUN_RESET_FAULT_TESTS(1'b0)
    ) u_src_fast_case (
        .done(src_fast_done)
    );

    rgb565_pg2l50h_pcie_mwr32_async_mailbox_case #(
        .CASE_ID(1),
        .SRC_HALF_PERIOD(9ns),
        .DST_HALF_PERIOD(5ns),
        .DST_START_PHASE(3ns),
        .RUN_RESET_FAULT_TESTS(1'b1)
    ) u_dst_fast_case (
        .done(dst_fast_done)
    );

    initial begin
        #100us;
        $fatal(1, "PCIe MWR32 asynchronous mailbox timeout");
    end

    initial begin
        wait (src_fast_done && dst_fast_done);
        $display("INFO: asynchronous mailbox CDC, ACK, and reset contracts verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

/**
 * @brief Run one clock-ratio scenario against an independent mailbox instance.
 *
 * @details
 * Three completed transactions force at least three request-token and
 * completion-token round trips, including both toggle polarities after the
 * initialized token value. CASE_ID 0 covers source-fast/destination-slow and
 * CASE_ID 1 covers source-slow/destination-fast. The latter also exercises
 * idle reset recovery and the documented in-flight reset fault boundary.
 */
module rgb565_pg2l50h_pcie_mwr32_async_mailbox_case #(
    parameter integer CASE_ID = 0,
    parameter time SRC_HALF_PERIOD = 4ns,
    parameter time DST_HALF_PERIOD = 7ns,
    parameter time DST_START_PHASE = 2ns,
    parameter bit RUN_RESET_FAULT_TESTS = 1'b0
) (
    output logic done
);
    localparam integer WAIT_LIMIT = 128;

    logic src_clk = 1'b0;
    logic src_rst_n = 1'b0;
    logic src_mwr32_req = 1'b0;
    logic src_mwr32_req_ack;
    logic [9:0] src_req_length = 10'd0;
    logic [63:0] src_req_addr = 64'd0;
    logic [31:0] src_req_data = 32'd0;
    logic src_channel_ready;
    logic src_fault_pulse;
    logic src_fault_sticky;

    logic dst_clk = 1'b0;
    logic dst_rst_n = 1'b0;
    logic dst_mwr32_req;
    logic dst_mwr32_req_ack = 1'b0;
    logic [9:0] dst_req_length;
    logic [63:0] dst_req_addr;
    logic [31:0] dst_req_data;
    logic dst_channel_ready;
    logic dst_fault_pulse;
    logic dst_fault_sticky;

    logic dst_req_previous = 1'b0;
    logic src_ack_previous = 1'b0;
    integer dst_issue_count = 0;
    integer src_ack_count = 0;

    /**
     * Expected DUT port contract:
     * - src_* belongs to the DDR core clock domain.
     * - dst_* belongs to the PCIe pclk_div2 domain.
     * - channel_ready is local-domain qualified and permits source acceptance
     *   only after both reset domains have completed their ready handshake.
     * - fault_pulse is a one-local-cycle event when an outstanding transaction
     *   loses its peer; fault_sticky records that event until local reset.
     */
    rgb565_pg2l50h_pcie_mwr32_async_mailbox u_dut (
        .src_rst_n(src_rst_n),
        .src_clk(src_clk),
        .src_mwr32_req(src_mwr32_req),
        .src_mwr32_req_ack(src_mwr32_req_ack),
        .src_req_length(src_req_length),
        .src_req_addr(src_req_addr),
        .src_req_data(src_req_data),
        .src_channel_ready(src_channel_ready),
        .src_fault_pulse(src_fault_pulse),
        .src_fault_sticky(src_fault_sticky),
        .dst_rst_n(dst_rst_n),
        .dst_clk(dst_clk),
        .dst_mwr32_req(dst_mwr32_req),
        .dst_mwr32_req_ack(dst_mwr32_req_ack),
        .dst_req_length(dst_req_length),
        .dst_req_addr(dst_req_addr),
        .dst_req_data(dst_req_data),
        .dst_channel_ready(dst_channel_ready),
        .dst_fault_pulse(dst_fault_pulse),
        .dst_fault_sticky(dst_fault_sticky)
    );

    always #(SRC_HALF_PERIOD) src_clk = ~src_clk;

    initial begin
        #(DST_START_PHASE);
        forever #(DST_HALF_PERIOD) dst_clk = ~dst_clk;
    end

    // Count request and completion activations rather than high cycles. These
    // counters make held request/ACK levels observable as duplicate transfers.
    always @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            dst_req_previous = 1'b0;
        end else begin
            #1ns;
            if (dst_mwr32_req && !dst_req_previous)
                dst_issue_count = dst_issue_count + 1;
            dst_req_previous = dst_mwr32_req;
        end
    end

    always @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            src_ack_previous = 1'b0;
        end else begin
            #1ns;
            if (src_mwr32_req_ack && !src_ack_previous)
                src_ack_count = src_ack_count + 1;
            src_ack_previous = src_mwr32_req_ack;
        end
    end

    task automatic wait_channel_ready;
        integer cycle_index;
        bit observed;
        begin
            observed = 1'b0;
            for (cycle_index = 0; cycle_index < WAIT_LIMIT; cycle_index = cycle_index + 1) begin
                @(posedge src_clk);
                #1ns;
                if (src_channel_ready && dst_channel_ready) begin
                    observed = 1'b1;
                    break;
                end
            end
            if (!observed)
                $fatal(1, "case %0d: channel-ready handshake timed out", CASE_ID);
        end
    endtask

    task automatic wait_destination_request;
        integer cycle_index;
        bit observed;
        begin
            observed = 1'b0;
            for (cycle_index = 0; cycle_index < WAIT_LIMIT; cycle_index = cycle_index + 1) begin
                @(posedge dst_clk);
                #1ns;
                if (dst_mwr32_req) begin
                    observed = 1'b1;
                    break;
                end
            end
            if (!observed)
                $fatal(1, "case %0d: destination request timed out", CASE_ID);
        end
    endtask

    task automatic wait_source_ack_high;
        integer cycle_index;
        bit observed;
        begin
            observed = 1'b0;
            for (cycle_index = 0; cycle_index < WAIT_LIMIT; cycle_index = cycle_index + 1) begin
                @(posedge src_clk);
                #1ns;
                if (src_mwr32_req_ack) begin
                    observed = 1'b1;
                    break;
                end
            end
            if (!observed)
                $fatal(1, "case %0d: source completion ACK timed out", CASE_ID);
        end
    endtask

    task automatic wait_source_ack_low;
        integer cycle_index;
        bit observed;
        begin
            observed = 1'b0;
            for (cycle_index = 0; cycle_index < WAIT_LIMIT; cycle_index = cycle_index + 1) begin
                @(posedge src_clk);
                #1ns;
                if (!src_mwr32_req_ack) begin
                    observed = 1'b1;
                    break;
                end
            end
            if (!observed)
                $fatal(1, "case %0d: held source ACK did not clear", CASE_ID);
        end
    endtask

    task automatic wait_src_fault_high;
        integer cycle_index;
        bit observed;
        begin
            observed = 1'b0;
            for (cycle_index = 0; cycle_index < WAIT_LIMIT; cycle_index = cycle_index + 1) begin
                @(posedge src_clk);
                #1ns;
                if (src_fault_pulse) begin
                    observed = 1'b1;
                    break;
                end
            end
            if (!observed)
                $fatal(1, "case %0d: source-domain in-flight reset fault timed out", CASE_ID);
        end
    endtask

    task automatic wait_dst_fault_high;
        integer cycle_index;
        bit observed;
        begin
            observed = 1'b0;
            for (cycle_index = 0; cycle_index < WAIT_LIMIT; cycle_index = cycle_index + 1) begin
                @(posedge dst_clk);
                #1ns;
                if (dst_fault_pulse) begin
                    observed = 1'b1;
                    break;
                end
            end
            if (!observed)
                $fatal(1, "case %0d: destination-domain in-flight reset fault timed out", CASE_ID);
        end
    endtask

    task automatic check_idle_outputs;
        begin
            if (src_mwr32_req_ack !== 1'b0 || dst_mwr32_req !== 1'b0 ||
                dst_mwr32_req_ack !== 1'b0 || src_fault_pulse !== 1'b0 ||
                src_fault_sticky !== 1'b0 || dst_fault_pulse !== 1'b0 ||
                dst_fault_sticky !== 1'b0)
                $fatal(1, "case %0d: mailbox was not idle", CASE_ID);
        end
    endtask

    /**
     * @brief Complete one source request and one real destination ACK.
     *
     * @details
     * Destination ACK is delayed while request/payload stability is checked,
     * then remains high for multiple cycles after destination request drops.
     * Source request remains high after returned ACK to prove WAIT_REQ_LOW
     * prevents recapture. Source readiness must stay low until the held
     * destination ACK is finally withdrawn, proving WAIT_ACK_LOW isolation.
     */
    task automatic run_transaction(
        input logic [9:0] expected_length,
        input logic [63:0] expected_addr,
        input logic [31:0] expected_data,
        input integer ack_delay_cycles,
        input integer ack_hold_cycles,
        input integer source_hold_cycles,
        input bit mutate_upstream_after_capture
    );
        integer cycle_index;
        integer issue_count_before;
        integer ack_count_before;
        begin
            wait_channel_ready();
            issue_count_before = dst_issue_count;
            ack_count_before = src_ack_count;

            @(negedge src_clk);
            if (!src_channel_ready)
                $fatal(1, "case %0d: source lost readiness before request launch", CASE_ID);
            src_req_length = expected_length;
            src_req_addr = expected_addr;
            src_req_data = expected_data;
            src_mwr32_req = 1'b1;
            @(posedge src_clk);
            #1ns;

            if (mutate_upstream_after_capture) begin
                @(negedge src_clk);
                src_req_length = ~expected_length;
                src_req_addr = ~expected_addr;
                src_req_data = ~expected_data;
            end

            wait_destination_request();
            if (dst_req_length !== expected_length || dst_req_addr !== expected_addr ||
                dst_req_data !== expected_data)
                $fatal(1, "case %0d: destination sampled a torn or live upstream payload", CASE_ID);
            if (dst_issue_count != issue_count_before + 1)
                $fatal(1, "case %0d: destination request activation count mismatch", CASE_ID);

            for (cycle_index = 0; cycle_index < ack_delay_cycles; cycle_index = cycle_index + 1) begin
                @(posedge dst_clk);
                #1ns;
                if (!dst_mwr32_req || dst_req_length !== expected_length ||
                    dst_req_addr !== expected_addr || dst_req_data !== expected_data)
                    $fatal(1, "case %0d: destination bundle changed before ACK", CASE_ID);
            end

            @(negedge dst_clk);
            dst_mwr32_req_ack = 1'b1;
            @(posedge dst_clk);
            #1ns;
            if (dst_mwr32_req)
                $fatal(1, "case %0d: destination request did not drop after ACK", CASE_ID);

            wait_source_ack_high();
            if (src_ack_count != ack_count_before + 1)
                $fatal(1, "case %0d: source completion activation count mismatch", CASE_ID);

            for (cycle_index = 0; cycle_index < source_hold_cycles; cycle_index = cycle_index + 1) begin
                @(posedge src_clk);
                #1ns;
                if (!src_mwr32_req_ack)
                    $fatal(1, "case %0d: source ACK did not remain high with held request", CASE_ID);
                if (dst_issue_count != issue_count_before + 1)
                    $fatal(1, "case %0d: held source request generated a duplicate transfer", CASE_ID);
            end

            @(negedge src_clk);
            src_mwr32_req = 1'b0;
            wait_source_ack_low();

            // A level-style vendor ACK may remain high after request removal.
            // No request or ready indication may leak through this dead time.
            for (cycle_index = 0; cycle_index < ack_hold_cycles; cycle_index = cycle_index + 1) begin
                @(posedge dst_clk);
                #1ns;
                if (dst_mwr32_req)
                    $fatal(1, "case %0d: held destination ACK caused a duplicate request", CASE_ID);
                if (src_channel_ready)
                    $fatal(1, "case %0d: source became ready before destination ACK returned low", CASE_ID);
            end

            @(negedge dst_clk);
            dst_mwr32_req_ack = 1'b0;
            wait_channel_ready();
            if (dst_issue_count != issue_count_before + 1 ||
                src_ack_count != ack_count_before + 1)
                $fatal(1, "case %0d: transaction was lost or duplicated", CASE_ID);
        end
    endtask

    task automatic test_idle_source_reset;
        integer issue_count_before;
        integer ack_count_before;
        begin
            wait_channel_ready();
            issue_count_before = dst_issue_count;
            ack_count_before = src_ack_count;
            @(negedge src_clk);
            src_rst_n = 1'b0;
            #1ns;
            if (src_channel_ready || src_mwr32_req_ack ||
                src_fault_pulse || src_fault_sticky)
                $fatal(1, "case %0d: source reset did not immediately quiesce source outputs", CASE_ID);
            repeat (5) @(posedge dst_clk);
            #1ns;
            if (dst_channel_ready || dst_fault_pulse || dst_fault_sticky ||
                dst_mwr32_req)
                $fatal(1, "case %0d: idle source reset caused target activity or fault", CASE_ID);
            @(negedge src_clk);
            src_rst_n = 1'b1;
            wait_channel_ready();
            if (dst_issue_count != issue_count_before || src_ack_count != ack_count_before)
                $fatal(1, "case %0d: idle source reset created a ghost transaction", CASE_ID);
        end
    endtask

    task automatic test_idle_destination_reset;
        integer issue_count_before;
        integer ack_count_before;
        begin
            wait_channel_ready();
            issue_count_before = dst_issue_count;
            ack_count_before = src_ack_count;
            @(negedge dst_clk);
            dst_rst_n = 1'b0;
            #1ns;
            if (dst_channel_ready || dst_mwr32_req ||
                dst_fault_pulse || dst_fault_sticky)
                $fatal(1, "case %0d: destination reset did not immediately quiesce outputs", CASE_ID);
            repeat (5) @(posedge src_clk);
            #1ns;
            if (src_channel_ready || src_fault_pulse || src_fault_sticky ||
                src_mwr32_req_ack)
                $fatal(1, "case %0d: idle destination reset caused source activity or fault", CASE_ID);
            @(negedge dst_clk);
            dst_rst_n = 1'b1;
            wait_channel_ready();
            if (dst_issue_count != issue_count_before || src_ack_count != ack_count_before)
                $fatal(1, "case %0d: idle destination reset created a ghost transaction", CASE_ID);
        end
    endtask

    task automatic test_inflight_source_reset_fault;
        integer issue_count_before;
        integer ack_count_before;
        begin
            wait_channel_ready();
            issue_count_before = dst_issue_count;
            ack_count_before = src_ack_count;
            @(negedge src_clk);
            src_req_length = 10'd1;
            src_req_addr = 64'h0000_0000_9000_0000;
            src_req_data = 32'h51ce_0001;
            src_mwr32_req = 1'b1;
            @(posedge src_clk);
            wait_destination_request();
            if (dst_issue_count != issue_count_before + 1)
                $fatal(1, "case %0d: source-reset setup request was not issued once", CASE_ID);

            @(negedge src_clk);
            src_rst_n = 1'b0;
            src_mwr32_req = 1'b0;
            wait_dst_fault_high();
            if (!dst_fault_sticky)
                $fatal(1, "case %0d: destination fault pulse did not set sticky state", CASE_ID);
            repeat (3) begin
                @(posedge dst_clk);
                #1ns;
                if (dst_fault_pulse || !dst_fault_sticky)
                    $fatal(1, "case %0d: destination fault pulse/sticky duration mismatch", CASE_ID);
            end
            if (dst_mwr32_req || dst_channel_ready || src_ack_count != ack_count_before)
                $fatal(1, "case %0d: source reset was silently completed or left target active", CASE_ID);

            // Both domains are reset before recovery; destination releases first
            // and must remain blocked until the source domain is also available.
            @(negedge dst_clk);
            dst_rst_n = 1'b0;
            #1ns;
            if (dst_fault_pulse || dst_fault_sticky)
                $fatal(1, "case %0d: destination local reset did not clear fault state", CASE_ID);
            repeat (3) @(posedge dst_clk);
            @(negedge dst_clk);
            dst_rst_n = 1'b1;
            repeat (4) @(posedge dst_clk);
            #1ns;
            if (dst_channel_ready || dst_fault_pulse || dst_fault_sticky)
                $fatal(1, "case %0d: destination reopened before source reset release", CASE_ID);
            @(negedge src_clk);
            src_rst_n = 1'b1;
            wait_channel_ready();
            if (src_fault_pulse || src_fault_sticky ||
                dst_fault_pulse || dst_fault_sticky ||
                src_mwr32_req_ack || dst_mwr32_req)
                $fatal(1, "case %0d: coordinated recovery retained stale source-reset state", CASE_ID);
        end
    endtask

    task automatic test_inflight_destination_reset_fault;
        integer issue_count_before;
        integer ack_count_before;
        begin
            wait_channel_ready();
            issue_count_before = dst_issue_count;
            ack_count_before = src_ack_count;
            @(negedge src_clk);
            src_req_length = 10'd2;
            src_req_addr = 64'h0000_0000_a000_0000;
            src_req_data = 32'h51ce_0002;
            src_mwr32_req = 1'b1;
            @(posedge src_clk);
            wait_destination_request();
            if (dst_issue_count != issue_count_before + 1)
                $fatal(1, "case %0d: destination-reset setup request was not issued once", CASE_ID);

            @(negedge dst_clk);
            dst_rst_n = 1'b0;
            wait_src_fault_high();
            if (!src_fault_sticky)
                $fatal(1, "case %0d: source fault pulse did not set sticky state", CASE_ID);
            repeat (3) begin
                @(posedge src_clk);
                #1ns;
                if (src_fault_pulse || !src_fault_sticky)
                    $fatal(1, "case %0d: source fault pulse/sticky duration mismatch", CASE_ID);
            end
            if (src_mwr32_req_ack || src_channel_ready || src_ack_count != ack_count_before)
                $fatal(1, "case %0d: destination reset was silently completed at source", CASE_ID);

            @(negedge src_clk);
            src_mwr32_req = 1'b0;
            src_rst_n = 1'b0;
            #1ns;
            if (src_fault_pulse || src_fault_sticky)
                $fatal(1, "case %0d: source local reset did not clear fault state", CASE_ID);
            repeat (3) @(posedge src_clk);
            @(negedge src_clk);
            src_rst_n = 1'b1;
            repeat (4) @(posedge src_clk);
            #1ns;
            if (src_channel_ready || src_fault_pulse || src_fault_sticky)
                $fatal(1, "case %0d: source reopened before destination reset release", CASE_ID);
            @(negedge dst_clk);
            dst_rst_n = 1'b1;
            wait_channel_ready();
            if (src_fault_pulse || src_fault_sticky ||
                dst_fault_pulse || dst_fault_sticky ||
                src_mwr32_req_ack || dst_mwr32_req)
                $fatal(1, "case %0d: coordinated recovery retained stale destination-reset state", CASE_ID);
        end
    endtask

    initial begin
        done = 1'b0;
        src_mwr32_req = 1'b0;
        dst_mwr32_req_ack = 1'b0;

        // Staggered initial release is an idle single-domain reset case. The
        // source must not accept traffic until destination readiness returns.
        repeat (3) @(posedge src_clk);
        @(negedge src_clk);
        src_rst_n = 1'b1;
        repeat (4) @(posedge src_clk);
        #1ns;
        if (src_channel_ready || src_mwr32_req_ack ||
            src_fault_pulse || src_fault_sticky)
            $fatal(1, "case %0d: source opened while destination remained reset", CASE_ID);
        repeat (2) @(posedge dst_clk);
        @(negedge dst_clk);
        dst_rst_n = 1'b1;
        wait_channel_ready();
        check_idle_outputs();

        run_transaction(10'd1, 64'h0000_0000_1000_0040, 32'h1122_3344,
                        3, 4, 3, 1'b1);
        run_transaction(10'd4, 64'h0000_0000_2000_0080, 32'ha5a5_5a5a,
                        1, 3, 4, 1'b0);
        run_transaction(10'd7, 64'h0000_0000_3000_00c0, 32'hdead_beef,
                        5, 2, 2, 1'b1);

        if (RUN_RESET_FAULT_TESTS) begin
            test_idle_source_reset();
            test_idle_destination_reset();
            test_inflight_source_reset_fault();
            test_inflight_destination_reset_fault();
        end

        check_idle_outputs();
        $display("INFO: mailbox clock-ratio case %0d completed", CASE_ID);
        done = 1'b1;
    end
endmodule

`default_nettype wire
