`timescale 1ns/1ps
module tb_fpga_v8_channel_copy;
    reg clk;
    reg rst_n;
    reg cmd_valid;
    wire cmd_ready;
    reg [31:0] cmd_total_pixels;
    reg [15:0] cmd_groups_per_pixel;
    reg [15:0] cmd_first_group;
    reg [15:0] cmd_group_count;
    wire cmd_error;
    reg s_valid;
    wire s_ready;
    reg [127:0] s_data;
    reg s_last;
    wire m_valid;
    reg m_ready;
    wire [127:0] m_data;
    wire m_last;
    wire busy;
    wire done;
    wire frame_error;

    fpga_v8_channel_copy dut (
        .clk(clk), .rst_n(rst_n),
        .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_total_pixels(cmd_total_pixels),
        .cmd_groups_per_pixel(cmd_groups_per_pixel),
        .cmd_first_group(cmd_first_group), .cmd_group_count(cmd_group_count),
        .cmd_error(cmd_error),
        .s_valid(s_valid), .s_ready(s_ready), .s_data(s_data), .s_last(s_last),
        .m_valid(m_valid), .m_ready(m_ready), .m_data(m_data), .m_last(m_last),
        .busy(busy), .done(done), .frame_error(frame_error)
    );

    reg [128:0] source_words [0:65535];
    reg [128:0] golden_words [0:65535];
    reg [128:0] stalled_word;
    reg previous_stall;
    reg source_hold;
    reg previous_done;
    reg scoreboard_enabled;
    reg expected_sticky_error;
    reg [31:0] random_state;
    reg [31:0] random_value;
    reg [2047:0] vector_root;
    reg [2047:0] filename;
    integer cases_file;
    integer output_file;
    integer summary_file;
    integer scan;
    integer case_id;
    integer pixels;
    integer groups;
    integer first;
    integer count;
    integer mode;
    integer expected_error;
    integer source_length;
    integer output_length;
    integer seed;
    integer source_index;
    integer output_index;
    integer done_count;
    integer cycle_index;
    integer gap_count;
    integer source_group;
    integer total_cases;
    integer total_source;
    integer total_output;
    integer total_cycles;
    integer skipped_while_stalled;
    integer selected_stalls;
    integer bubbles;
    integer output_stalls;
    integer replacements;
    integer invalid_count;
    integer reset_count;
    integer directed_waits;
    integer commands_while_busy;
    integer post_done_cycles;
    reg fired_input;
    reg fired_output;
    reg pre_busy;
    reg pre_command_fire;

    always #5 clk = !clk;

    task fail;
        input [2047:0] message;
        begin
            $display("FAIL case=%0d cycle=%0d src=%0d out=%0d: %0s",
                     case_id, cycle_index, source_index, output_index, message);
            $finish(1);
        end
    endtask

    task next_random;
        begin
            random_state = random_state ^ (random_state << 13);
            random_state = random_state ^ (random_state >> 17);
            random_state = random_state ^ (random_state << 5);
            random_value = random_state;
        end
    endtask

    // Every driven cycle is checked both before and after registered updates.
    task tick;
        begin
            @(posedge clk);
            total_cycles = total_cycles + 1;
            fired_input = s_valid && s_ready;
            fired_output = m_valid && m_ready;
            pre_busy = busy;
            pre_command_fire = cmd_valid && cmd_ready;
            if (rst_n) begin
                if (cmd_ready && (busy || m_valid || done))
                    fail("command ready before old completion drained");
                if (s_ready && !busy)
                    fail("source ready without an active command");
                if (previous_stall &&
                    (!m_valid || {m_last, m_data} !== stalled_word))
                    fail("pending output changed under backpressure");
                if (busy && cmd_valid) begin
                    commands_while_busy = commands_while_busy + 1;
                    if (pre_command_fire)
                        fail("accepted command while old transaction busy");
                end
                if (scoreboard_enabled) begin
                    if (fired_input) begin
                        if (source_index >= source_length)
                            fail("consumed beyond the declared input word count");
                        if ({s_last, s_data} !== source_words[source_index])
                            fail("source driver changed a held input word");
                        if (s_last != (source_index == source_length - 1))
                            expected_sticky_error = 1;
                        source_index = source_index + 1;
                        total_source = total_source + 1;
                    end
                    if (fired_output) begin
                        if (output_index >= output_length)
                            fail("extra output word");
                        if ({m_last, m_data} !== golden_words[output_index]) begin
                            $display("actual=%033h expected=%033h",
                                     {m_last, m_data}, golden_words[output_index]);
                            fail("complete output data/last differs from Python golden");
                        end
                        $fdisplay(output_file, "%033h", {m_last, m_data});
                        output_index = output_index + 1;
                        total_output = total_output + 1;
                    end
                    if (pre_busy && source_index < source_length + fired_input) begin
                        source_group = (source_index - fired_input) % groups;
                        if (m_valid && !m_ready) begin
                            output_stalls = output_stalls + 1;
                            if (source_group < first || source_group >= first + count) begin
                                if (!s_ready)
                                    fail("skipped input blocked by a pending selected output");
                                if (fired_input)
                                    skipped_while_stalled = skipped_while_stalled + 1;
                            end else begin
                                if (s_ready)
                                    fail("selected input can overwrite a stalled output");
                                selected_stalls = selected_stalls + 1;
                            end
                        end
                    end
                    if (fired_input && fired_output)
                        replacements = replacements + 1;
                    if (pre_busy && !s_valid && source_index < source_length)
                        bubbles = bubbles + 1;
                end else if (fired_output) begin
                    fail("ghost output outside a scored transaction");
                end
            end
            previous_stall = rst_n && m_valid && !m_ready;
            stalled_word = {m_last, m_data};
            source_hold = rst_n && s_valid && !s_ready;
            #1;
            if (!rst_n) begin
                if (busy || done || m_valid || cmd_error || frame_error || s_ready || cmd_ready)
                    fail("reset did not clear transaction and gate ready");
                previous_stall = 0;
                previous_done = 0;
                source_hold = 0;
            end else begin
                if (scoreboard_enabled && pre_busy &&
                    frame_error !== expected_sticky_error)
                    fail("frame error is not handshake-qualified and sticky");
                if (done) begin
                    if (previous_done)
                        fail("done is longer than one cycle");
                    if (!scoreboard_enabled)
                        fail("ghost completion");
                    if (source_index != source_length || output_index != output_length)
                        fail("done before both complete source and complete output");
                    if (busy || m_valid || s_ready || cmd_ready)
                        fail("done has a pending transaction or ready command");
                    done_count = done_count + 1;
                end
                previous_done = done;
            end
        end
    endtask

    task idle_cycle;
        begin
            @(negedge clk);
            cmd_valid = 0;
            s_valid = 0;
            s_last = 1;
            m_ready = 1;
            tick;
        end
    endtask

    task reset_idle;
        begin
            @(negedge clk);
            rst_n = 0;
            cmd_valid = 1;
            s_valid = 1;
            s_last = 1;
            m_ready = 1;
            tick;
            @(negedge clk);
            cmd_valid = 0;
            s_valid = 0;
            rst_n = 1;
            tick;
            if (!cmd_ready || busy || m_valid || done)
                fail("not idle after reset release");
        end
    endtask

    task bad_command;
        input [31:0] bad_pixels;
        input [15:0] bad_groups;
        input [15:0] bad_first;
        input [15:0] bad_count;
        begin
            @(negedge clk);
            if (!cmd_ready) fail("invalid command test not ready");
            cmd_valid = 1;
            cmd_total_pixels = bad_pixels;
            cmd_groups_per_pixel = bad_groups;
            cmd_first_group = bad_first;
            cmd_group_count = bad_count;
            s_valid = 1;
            s_last = 1;
            tick;
            if (!cmd_error || busy || m_valid || done || !cmd_ready || s_ready)
                fail("invalid configuration was not rejected without starting");
            idle_cycle;
            if (cmd_error || busy || m_valid || done)
                fail("cmd_error is not a pulse");
            invalid_count = invalid_count + 1;
        end
    endtask

    // Abort a selected word while stalled, both before and after source end.
    // Also exercise maximum pixel-count width and reset after a framing error.
    task reset_pending;
        input integer kind;
        integer n;
        integer k;
        begin
            @(negedge clk);
            cmd_valid = 1;
            cmd_total_pixels = (kind == 2) ? 32'hffffffff : 32'd1;
            cmd_groups_per_pixel = (kind == 1) ? 16'd4 : 16'd1;
            cmd_first_group = 0;
            cmd_group_count = 1;
            s_valid = 0;
            m_ready = 0;
            tick;
            if (!busy || !s_ready || frame_error)
                fail("reset-pending command did not start cleanly");
            n = (kind == 1) ? 4 : 1;
            for (k = 0; k < n; k = k + 1) begin
                @(negedge clk);
                cmd_valid = 0;
                s_valid = 1;
                s_data = 128'hfedcba98765432100123456789abcdef + k;
                s_last = (kind == 3) ? 0 : (k == n - 1);
                tick;
            end
            if (!m_valid || !busy || done)
                fail("reset test has no stalled selected output");
            if (kind == 2 && !frame_error)
                fail("early last did not mark the maximum-pixel command");
            if (kind == 3 && !frame_error)
                fail("missing final last did not flag before reset");
            // Asynchronous reset between edges must remove pending valid now.
            @(negedge clk);
            rst_n = 0;
            cmd_valid = 1;
            s_valid = 1;
            m_ready = 1;
            #1;
            if (m_valid || busy || done || frame_error || cmd_error || cmd_ready || s_ready)
                fail("asynchronous reset left a ghost pending transaction");
            tick;
            @(negedge clk);
            rst_n = 1;
            cmd_valid = 0;
            s_valid = 0;
            tick;
            repeat (4) idle_cycle;
            if (!cmd_ready || busy || done || m_valid || frame_error)
                fail("reset leaked a discarded selected word");
            reset_count = reset_count + 1;
        end
    endtask

    task run_case;
        begin
            $sformat(filename, "%0s/case_%0d_input.hex", vector_root, case_id);
            $readmemh(filename, source_words, 0, source_length - 1);
            $sformat(filename, "%0s/case_%0d_expected.hex", vector_root, case_id);
            $readmemh(filename, golden_words, 0, output_length - 1);
            $sformat(filename, "%0s/case_%0d_actual.hex", vector_root, case_id);
            output_file = $fopen(filename, "w");
            if (!output_file) fail("could not open actual output file");
            source_index = 0;
            output_index = 0;
            done_count = 0;
            gap_count = 0;
            source_hold = 0;
            random_state = seed;
            scoreboard_enabled = 1;
            expected_sticky_error = 0;
            while (!cmd_ready) idle_cycle;
            @(negedge clk);
            cmd_valid = 1;
            cmd_total_pixels = pixels;
            cmd_groups_per_pixel = groups;
            cmd_first_group = first;
            cmd_group_count = count;
            s_valid = 0;
            m_ready = 0;
            tick;
            if (!busy || cmd_error || frame_error)
                fail("valid command did not snapshot and clear frame error");
            cycle_index = 0;
            while (done_count == 0 && cycle_index < source_length * 30 + 500) begin
                @(negedge clk);
                cycle_index = cycle_index + 1;
                next_random;
                // Change every live command field after acceptance.
                // Mode 4 additionally keeps a stable waiting command valid.
                cmd_valid = (mode == 4);
                cmd_total_pixels = (mode == 4) ? pixels : random_value;
                cmd_groups_per_pixel = (mode == 4) ? groups : random_value[15:0];
                cmd_first_group = (mode == 4) ? first : random_value[31:16];
                cmd_group_count = (mode == 4) ? count : 16'd0;
                if (mode == 0 || mode == 5) begin
                    m_ready = (random_value[3:0] >= 5);
                    if ((cycle_index % 71) < 13) m_ready = 0;
                end else begin
                    m_ready = !((mode == 2 || mode == 3) && cycle_index <= 25);
                end
                next_random;
                s_valid = 0;
                s_data = 128'h0123456789abcdeffedcba9876543210;
                s_last = 1; // Invalid cycles must not change frame_error.
                if (source_index < source_length) begin
                    s_valid = source_hold || mode != 0 && mode != 5 || random_value[2:0] >= 2;
                    s_data = source_words[source_index][127:0];
                    s_last = source_words[source_index][128];
                    if (mode == 1 && output_index == output_length && gap_count < 12) begin
                        s_valid = 0;
                        gap_count = gap_count + 1;
                        if (!busy || done || cmd_ready)
                            fail("finished on final output before trailing skipped source");
                        directed_waits = directed_waits + 1;
                    end
                end else if (mode == 5) begin
                    // A late s_last beyond the command cannot consume a word.
                    s_valid = 1;
                    s_last = 1;
                end
                if (mode == 2 && source_index == source_length && output_index == 0) begin
                    if (!busy || done || cmd_ready || s_ready)
                        fail("finished with a stalled final output after source end");
                    directed_waits = directed_waits + 1;
                end
                tick;
            end
            if (done_count != 1) fail("timeout or missing completion");
            if (source_index != source_length || output_index != output_length)
                fail("word sequence was truncated");
            if (frame_error !== (expected_error != 0))
                fail("final frame error differs from case expectation");
            // Keep watching after completion: no second done or extra data.
            for (post_done_cycles = 0; post_done_cycles < 8; post_done_cycles = post_done_cycles + 1) begin
                @(negedge clk);
                cmd_valid = 0;
                s_valid = (mode == 5);
                s_last = 1;
                m_ready = 1;
                tick;
                if (busy || m_valid || done || s_ready || cmd_error || !cmd_ready)
                    fail("old transaction produced data or completion after done");
                if (frame_error !== (expected_error != 0))
                    fail("frame error did not stay sticky after completion");
            end
            if (done_count != 1) fail("duplicate done pulse");
            $fclose(output_file);
            scoreboard_enabled = 0;
            total_cases = total_cases + 1;
            $display("PASS_CASE %0d source=%0d output=%0d frame_error=%0d cycles=%0d",
                     case_id, source_index, output_index, frame_error, cycle_index);
        end
    endtask

    initial begin
        clk = 0;
        rst_n = 0;
        cmd_valid = 0;
        cmd_total_pixels = 0;
        cmd_groups_per_pixel = 0;
        cmd_first_group = 0;
        cmd_group_count = 0;
        s_valid = 0;
        s_data = 0;
        s_last = 0;
        m_ready = 0;
        previous_stall = 0;
        previous_done = 0;
        source_hold = 0;
        scoreboard_enabled = 0;
        expected_sticky_error = 0;
        case_id = -1;
        cycle_index = 0;
        source_index = 0;
        output_index = 0;
        total_cases = 0;
        total_source = 0;
        total_output = 0;
        total_cycles = 0;
        skipped_while_stalled = 0;
        selected_stalls = 0;
        bubbles = 0;
        output_stalls = 0;
        replacements = 0;
        invalid_count = 0;
        reset_count = 0;
        directed_waits = 0;
        commands_while_busy = 0;
        if (!$value$plusargs("VECTORS=%s", vector_root))
            fail("missing VECTORS plusarg");
        reset_idle;
        bad_command(0, 4, 0, 1);
        bad_command(1, 0, 0, 1);
        bad_command(1, 4, 0, 0);
        bad_command(1, 4, 4, 1);
        bad_command(1, 4, 3, 2);
        bad_command(1, 4, 0, 5);
        bad_command(1, 4, 16'hffff, 1);
        bad_command(1, 16'hffff, 16'hfffe, 2);
        bad_command(1, 16'hffff, 16'hffff, 16'hffff);
        reset_pending(0);
        reset_pending(1);
        reset_pending(2);
        reset_pending(3);
        $sformat(filename, "%0s/cases.txt", vector_root);
        cases_file = $fopen(filename, "r");
        if (!cases_file) fail("could not open case list");
        scan = $fscanf(cases_file, "%d %d %d %d %d %d %d %d %d %d\n",
                       case_id, pixels, groups, first, count, mode,
                       expected_error, source_length, output_length, seed);
        while (scan == 10) begin
            run_case;
            scan = $fscanf(cases_file, "%d %d %d %d %d %d %d %d %d %d\n",
                           case_id, pixels, groups, first, count, mode,
                           expected_error, source_length, output_length, seed);
        end
        if (!$feof(cases_file)) fail("malformed case-list line");
        $fclose(cases_file);
        if (total_cases == 0 || skipped_while_stalled == 0 || selected_stalls == 0 ||
            bubbles == 0 || output_stalls == 0 || replacements == 0 ||
            directed_waits < 12 || commands_while_busy == 0 ||
            invalid_count != 9 || reset_count != 4)
            fail("required protocol coverage missing");
        $sformat(filename, "%0s/simulation_stats.txt", vector_root);
        summary_file = $fopen(filename, "w");
        $fdisplay(summary_file, "cases %0d", total_cases);
        $fdisplay(summary_file, "source_words %0d", total_source);
        $fdisplay(summary_file, "output_words %0d", total_output);
        $fdisplay(summary_file, "cycles %0d", total_cycles);
        $fdisplay(summary_file, "invalid_commands %0d", invalid_count);
        $fdisplay(summary_file, "reset_pending %0d", reset_count);
        $fdisplay(summary_file, "skipped_while_stalled %0d", skipped_while_stalled);
        $fdisplay(summary_file, "selected_stalls %0d", selected_stalls);
        $fdisplay(summary_file, "source_bubbles %0d", bubbles);
        $fdisplay(summary_file, "output_stalls %0d", output_stalls);
        $fdisplay(summary_file, "simultaneous_input_output %0d", replacements);
        $fdisplay(summary_file, "directed_completion_waits %0d", directed_waits);
        $fdisplay(summary_file, "waiting_command_cycles %0d", commands_while_busy);
        $fclose(summary_file);
        $display("PASS_SIM cases=%0d input_words=%0d output_words=%0d invalid=%0d reset=%0d",
                 total_cases, total_source, total_output, invalid_count, reset_count);
        $finish;
    end
endmodule
