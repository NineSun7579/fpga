`timescale 1ns/1ps
module tb_fpga_v8_activation_lut;
    parameter LANES = 16;
    reg clk = 1'b0;
    always #5 clk = !clk;
    reg rst;
    reg cfg_valid;
    wire cfg_ready;
    reg [7:0] cfg_addr;
    reg [7:0] cfg_data;
    reg s_valid;
    wire s_ready;
    reg [LANES*8-1:0] s_data;
    reg s_last;
    reg bypass;
    wire m_valid;
    reg m_ready;
    wire [LANES*8-1:0] m_data;
    wire m_last;

    fpga_v8_activation_lut #(.LANES(LANES)) dut (
        .clk(clk), .rst(rst), .cfg_valid(cfg_valid), .cfg_ready(cfg_ready),
        .cfg_addr(cfg_addr), .cfg_data(cfg_data),
        .s_valid(s_valid), .s_ready(s_ready), .s_data(s_data), .s_last(s_last),
        .bypass(bypass), .m_valid(m_valid), .m_ready(m_ready),
        .m_data(m_data), .m_last(m_last)
    );

    reg [7:0] table_a [0:255];
    reg [7:0] table_b [0:255];
    reg [7:0] model_table [0:255];
    integer coverage_a [0:LANES*256-1];
    integer coverage_b [0:LANES*256-1];
    integer coverage_bypass [0:LANES*256-1];
    reg model_valid;
    reg [LANES*8-1:0] model_data;
    reg model_last;
    reg old_stall;
    reg [LANES*8-1:0] held_data;
    reg held_last;
    reg last_input_fire;
    reg sampled_input_fire;
    reg sampled_output_fire;
    integer active_table;
    integer accepted;
    integer received;
    integer dropped;
    integer writes;
    integer rejected;
    integer stalls;
    integer simultaneous;
    integer priority_checks;
    integer latency_checks;
    integer last_received;
    integer reset_cycles;
    integer cycles;
    integer monitor_lane;
    integer monitor_code;
    integer init_index;
    reg [31:0] random_state;
    integer seed;

    task fail;
        input [8*160-1:0] reason;
        begin
            $display("FAIL LANES=%0d cycle=%0d time=%0t: %0s", LANES, cycles, $time, reason);
            $finish;
        end
    endtask

    // The reference observes public handshakes and accepted configuration only.
    // Compare both before the edge and after NBA updates to enforce one-cycle
    // lookup, exact occupancy, table contents, and stability through every stall.
    always @(posedge clk) begin
        cycles = cycles + 1;
        sampled_input_fire = s_valid && s_ready;
        sampled_output_fire = m_valid && m_ready;
        last_input_fire = sampled_input_fire;
        if (rst) begin
            if (s_ready !== 1'b0 || cfg_ready !== 1'b0)
                fail("ready asserted during reset");
            if (model_valid)
                dropped = dropped + 1;
            model_valid = 1'b0;
            old_stall = 1'b0;
            reset_cycles = reset_cycles + 1;
            #1;
            if (m_valid !== 1'b0 || m_last !== 1'b0 || m_data !== {LANES*8{1'b0}})
                fail("synchronous reset did not clear output state");
        end else begin
            if (cfg_ready !== !model_valid)
                fail("cfg_ready must mean output empty");
            if (s_ready !== (!cfg_valid && (!model_valid || m_ready)))
                fail("s_ready violates elastic capacity/configuration priority");
            if (m_valid !== model_valid)
                fail("unexpected output occupancy before edge");
            if (model_valid && (m_data !== model_data || m_last !== model_last)) begin
                $display("EXPECTED data=%h last=%b ACTUAL data=%h last=%b",
                         model_data, model_last, m_data, m_last);
                fail("output differs from handshake/table reference");
            end
            if (old_stall && (m_valid !== 1'b1 || m_data !== held_data || m_last !== held_last))
                fail("pending output changed under backpressure");
            old_stall = m_valid && !m_ready;
            if (old_stall) begin
                held_data = m_data;
                held_last = m_last;
                stalls = stalls + 1;
            end
            if (cfg_valid && !cfg_ready)
                rejected = rejected + 1;
            if (cfg_valid && cfg_ready) begin
                if (model_valid || sampled_input_fire)
                    fail("configuration accepted with a transaction in flight");
                model_table[cfg_addr] = cfg_data;
                writes = writes + 1;
                if (s_valid) begin
                    if (s_ready !== 1'b0)
                        fail("configuration and source accepted together");
                    priority_checks = priority_checks + 1;
                end
            end
            if (sampled_output_fire) begin
                received = received + 1;
                if (m_last)
                    last_received = last_received + 1;
                model_valid = 1'b0;
            end
            if (sampled_input_fire) begin
                if (model_valid)
                    fail("accepted input overwrites a pending output");
                for (monitor_lane = 0; monitor_lane < LANES; monitor_lane = monitor_lane + 1) begin
                    monitor_code = s_data[monitor_lane*8 +: 8];
                    if (bypass) begin
                        model_data[monitor_lane*8 +: 8] = monitor_code;
                        coverage_bypass[monitor_lane*256 + monitor_code] =
                            coverage_bypass[monitor_lane*256 + monitor_code] + 1;
                    end else begin
                        model_data[monitor_lane*8 +: 8] = model_table[monitor_code];
                        if (active_table == 0)
                            coverage_a[monitor_lane*256 + monitor_code] =
                                coverage_a[monitor_lane*256 + monitor_code] + 1;
                        else if (active_table == 1)
                            coverage_b[monitor_lane*256 + monitor_code] =
                                coverage_b[monitor_lane*256 + monitor_code] + 1;
                        else
                            fail("non-bypass input before table programming");
                    end
                end
                model_last = s_last;
                model_valid = 1'b1;
                accepted = accepted + 1;
            end
            if (sampled_input_fire && sampled_output_fire)
                simultaneous = simultaneous + 1;
            #1;
            if (m_valid !== model_valid)
                fail("wrong occupancy after edge: lookup latency must be one cycle");
            if (model_valid && (m_data !== model_data || m_last !== model_last))
                fail("registered lookup/last mismatch after edge");
            if (sampled_input_fire)
                latency_checks = latency_checks + 1;
        end
    end

    task cycle;
        input do_reset;
        input do_config;
        input [7:0] addr;
        input [7:0] value;
        input valid;
        input [LANES*8-1:0] payload;
        input last;
        input identity;
        input ready;
        begin
            @(negedge clk);
            rst = do_reset;
            cfg_valid = do_config;
            cfg_addr = addr;
            cfg_data = value;
            s_valid = valid;
            s_data = payload;
            s_last = last;
            bypass = identity;
            m_ready = ready;
            @(posedge clk);
            #2;
        end
    endtask

    task idle;
        begin
            cycle(0, 0, 0, 0, 0, {LANES*8{1'b0}}, 0, 0, 1);
        end
    endtask

    task drain;
        integer drain_count;
        begin
            drain_count = 0;
            while (model_valid) begin
                idle;
                drain_count = drain_count + 1;
                if (drain_count > 2)
                    fail("one-slot pipeline did not drain");
            end
        end
    endtask

    task program_table;
        input which;
        integer addr;
        reg [7:0] value;
        begin
            drain;
            active_table = which;
            for (addr = 0; addr < 256; addr = addr + 1) begin
                value = which ? table_b[addr] : table_a[addr];
                // Offer input at the same time: configuration must win.
                cycle(0, 1, addr, value, 1, {LANES{8'h5a}}, 1, 0, 1);
            end
            idle;
        end
    endtask

    task next_random;
        begin
            random_state = random_state * 32'd1664525 + 32'd1013904223;
        end
    endtask

    // mode 0: LUT, mode 1: identity, mode 2: change bypass each accepted beat.
    // First 256 LUT beats run continuously to check full-rate replacement.
    // Later beats have deterministic random sink stalls and source bubbles.
    task stream;
        input integer count;
        input integer mode;
        integer beat;
        integer lane;
        integer attempts;
        reg [LANES*8-1:0] payload;
        reg last;
        reg identity;
        reg ready;
        begin
            for (beat = 0; beat < count; beat = beat + 1) begin
                for (lane = 0; lane < LANES; lane = lane + 1)
                    payload[lane*8 +: 8] = (beat + lane*17) & 255;
                last = ((beat % 19) == 18) || (beat == count-1);
                identity = (mode == 1) || ((mode == 2) && ((beat % 2) == 1));
                attempts = 0;
                begin : send_until_accepted
                    forever begin
                        next_random;
                        ready = ((mode == 0) && (beat < 256)) || (random_state[31:28] >= 6);
                        cycle(0, 0, 0, 0, 1, payload, last, identity, ready);
                        attempts = attempts + 1;
                        if (last_input_fire)
                            disable send_until_accepted;
                        if (attempts > 100)
                            fail("random source could not make progress");
                    end
                end
                next_random;
                if ((mode != 0 || beat >= 256) && random_state[31:28] < 3)
                    cycle(0, 0, 0, 0, 0, {LANES{8'hff}}, 0, !identity, random_state[10]);
            end
            drain;
        end
    endtask

    task rejected_config_test;
        integer attempt;
        begin
            drain;
            // Output includes entry zero on every lane; keep it pending.
            cycle(0, 0, 0, 0, 1, {LANES{8'h00}}, 1, 0, 0);
            for (attempt = 0; attempt < 8; attempt = attempt + 1)
                cycle(0, 1, 0, model_table[0] ^ 8'hff, 1, {LANES{8'hff}}, 0, 1, 0);
            // Pending output consuming now still disallows a configuration write.
            cycle(0, 1, 0, model_table[0] ^ 8'hff, 1, {LANES{8'hff}}, 0, 1, 1);
            // Re-read the rejected address to detect a hidden memory mutation.
            cycle(0, 0, 0, 0, 1, {LANES{8'h00}}, 0, 0, 1);
            drain;
        end
    endtask

    task reset_pending_test;
        begin
            drain;
            cycle(0, 0, 0, 0, 1, {LANES{8'h00}}, 1, 0, 0);
            cycle(0, 0, 0, 0, 0, {LANES{8'hff}}, 0, 1, 0);
            // Reset discards one pending result and must not program the table.
            cycle(1, 1, 0, model_table[0] ^ 8'hff, 1, {LANES{8'hff}}, 1, 1, 1);
            cycle(1, 1, 0, model_table[0] ^ 8'hff, 1, {LANES{8'hff}}, 1, 0, 1);
            cycle(0, 0, 0, 0, 1, {LANES{8'h00}}, 0, 0, 1);
            drain;
        end
    endtask

    initial begin
        rst = 1;
        cfg_valid = 0;
        cfg_addr = 0;
        cfg_data = 0;
        s_valid = 0;
        s_data = 0;
        s_last = 0;
        bypass = 0;
        m_ready = 0;
        model_valid = 0;
        model_data = 0;
        model_last = 0;
        old_stall = 0;
        last_input_fire = 0;
        active_table = -1;
        accepted = 0;
        received = 0;
        dropped = 0;
        writes = 0;
        rejected = 0;
        stalls = 0;
        simultaneous = 0;
        priority_checks = 0;
        latency_checks = 0;
        last_received = 0;
        reset_cycles = 0;
        cycles = 0;
        seed = 20260929;
        if ($value$plusargs("seed=%d", seed)) begin end
        random_state = seed;
        for (init_index = 0; init_index < LANES*256; init_index = init_index + 1) begin
            coverage_a[init_index] = 0;
            coverage_b[init_index] = 0;
            coverage_bypass[init_index] = 0;
        end
        $readmemh("table_a.hex", table_a);
        $readmemh("table_b.hex", table_b);
        for (init_index = 0; init_index < 256; init_index = init_index + 1)
            if ((^table_a[init_index] === 1'bx) || (^table_b[init_index] === 1'bx))
                fail("missing or invalid table files");
        $display("START LANES=%0d seed=%0d", LANES, seed);
        cycle(1, 0, 0, 0, 0, {LANES*8{1'b0}}, 0, 0, 0);
        idle;
        stream(256, 1); // Identity must work before any programming.
        program_table(0);
        stream(512, 0);
        rejected_config_test;
        stream(128, 2);
        reset_pending_test;
        program_table(1);
        stream(512, 0);
        rejected_config_test;
        stream(256, 1);
        stream(128, 2);
        reset_pending_test;
        stream(256, 0); // Full table readback verifies retention across reset.
        drain;
        idle;
        for (init_index = 0; init_index < LANES*256; init_index = init_index + 1) begin
            if (coverage_a[init_index] < 2 || coverage_b[init_index] < 3 || coverage_bypass[init_index] < 2)
                fail("not every code was verified on every lane");
        end
        if (accepted != received + dropped || dropped != 2 || model_valid)
            fail("transaction conservation or reset-discard count failed");
        if (writes != 512 || rejected != 18 || priority_checks != 512)
            fail("configuration acceptance/rejection coverage failed");
        if (latency_checks != accepted || stalls < 100 || simultaneous < 765 || last_received < 50)
            fail("latency/stall/full-throughput/last coverage failed");
        $display("COVERAGE LANES=%0d table_a_codes_per_lane=256 min_visits=2 table_b_codes_per_lane=256 min_visits=3 bypass_codes_per_lane=256 min_visits=2", LANES);
        $display("COUNTERS accepted=%0d received=%0d reset_discarded=%0d writes=%0d rejected=%0d priority_checks=%0d", accepted, received, dropped, writes, rejected, priority_checks);
        $display("COUNTERS stalls=%0d simultaneous_io=%0d one_cycle_checks=%0d last_received=%0d reset_cycles=%0d cycles=%0d", stalls, simultaneous, latency_checks, last_received, reset_cycles, cycles);
        $display("PASS fpga_v8_activation_lut LANES=%0d seed=%0d", LANES, seed);
        $finish;
    end

    initial begin
        #2000000;
        fail("watchdog timeout");
    end
endmodule
