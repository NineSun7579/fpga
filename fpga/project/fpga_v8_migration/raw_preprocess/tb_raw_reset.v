`timescale 1ns/1ps
module tb_raw_reset;
    reg clk = 1'b0;
    always #5 clk = !clk;
    reg rst_n = 1'b0;
    reg start_valid = 1'b0;
    wire start_ready, busy, done, frame_error, config_error;
    reg [15:0] raw_data = 16'd0;
    reg raw_valid = 1'b0;
    reg raw_last = 1'b0;
    wire raw_ready;
    wire [23:0] rgb_data;
    wire rgb_valid, rgb_ready, rgb_last;
    wire [127:0] packed_data;
    wire [15:0] packed_keep;
    wire packed_valid, packed_last;
    reg packed_ready = 1'b0;
    reg direct_rst_n = 1'b0;
    reg [23:0] direct_data = 24'd0;
    reg direct_valid = 1'b0;
    reg direct_last = 1'b0;
    wire direct_ready;
    wire [127:0] direct_out;
    wire [15:0] direct_keep;
    wire direct_out_valid, direct_out_last;
    reg direct_out_ready = 1'b0;
    reg [15:0] sources [0:11];
    reg [127:0] words [0:3];
    reg [15:0] keeps [0:3];
    integer i, wait_count;
    integer output_count = 0;
    integer source_count = 0;
    integer done_count = 0;
    integer direct_count = 0;
    reg checking = 1'b0;
    reg direct_checking = 1'b0;

    fpga_v8_raw_letterbox #(.WIDTH(4), .HEIGHT(3), .OUT_HEIGHT(5), .TOP_ROWS(1)) dut (
        .clk(clk), .rst_n(rst_n), .start_valid(start_valid), .start_ready(start_ready),
        .busy(busy), .done(done), .frame_error(frame_error), .config_error(config_error),
        .s_data(raw_data), .s_valid(raw_valid), .s_ready(raw_ready), .s_last(raw_last),
        .m_data(rgb_data), .m_valid(rgb_valid), .m_ready(rgb_ready), .m_last(rgb_last));
    fpga_v8_rgb888_pack128 packer (
        .clk(clk), .rst_n(rst_n), .s_data(rgb_data), .s_valid(rgb_valid),
        .s_ready(rgb_ready), .s_last(rgb_last), .m_data(packed_data),
        .m_keep(packed_keep), .m_valid(packed_valid), .m_ready(packed_ready),
        .m_last(packed_last));
    fpga_v8_rgb888_pack128 direct (
        .clk(clk), .rst_n(direct_rst_n), .s_data(direct_data), .s_valid(direct_valid),
        .s_ready(direct_ready), .s_last(direct_last), .m_data(direct_out),
        .m_keep(direct_keep), .m_valid(direct_out_valid), .m_ready(direct_out_ready),
        .m_last(direct_out_last));
    task fail;
        input [511:0] reason;
        begin $display("FAIL reset: %0s", reason); $finish; end
    endtask
    task reset_direct;
        begin
            @(negedge clk);
            direct_rst_n = 1'b0;
            direct_valid = 1'b0;
            #1;
            if (direct_out_valid || direct_ready) fail("Direct reset did not clear pending output");
            repeat (2) @(negedge clk);
            direct_rst_n = 1'b1;
            direct_out_ready = 1'b1;
            repeat (5) begin
                @(negedge clk);
                if (direct_out_valid) fail("Ghost direct output after reset");
            end
        end
    endtask
    task send_direct;
        input [23:0] data;
        input last;
        begin
            @(negedge clk);
            direct_data = data;
            direct_last = last;
            direct_valid = 1'b1;
            @(posedge clk);
            while (!direct_ready) @(posedge clk);
            @(negedge clk);
            direct_valid = 1'b0;
        end
    endtask
    always @(posedge clk) begin
        if (rst_n && checking) begin
            if (raw_valid && raw_ready) source_count = source_count + 1;
            if (packed_valid && packed_ready) begin
                if (output_count >= 4 || packed_data !== words[output_count] ||
                    packed_keep !== keeps[output_count] || packed_last != (output_count == 3))
                    fail("Restarted integrated frame differs from golden");
                output_count = output_count + 1;
            end
            #1;
            if (done) done_count = done_count + 1;
        end
    end
    always @(posedge clk) begin
        if (direct_rst_n && direct_checking && direct_out_valid && direct_out_ready) begin
            if (direct_out !== 128'h00000000000000000000000000332211 ||
                direct_keep !== 16'h0007 || !direct_out_last || direct_count != 0)
                fail("Direct restart contaminated by pre-reset bytes");
            direct_count = direct_count + 1;
        end
    end
    initial begin
        $readmemh("source.hex", sources);
        $readmemh("words.hex", words);
        $readmemh("keeps.hex", keeps);
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        raw_valid = 1'b1;
        raw_last = 1'b1;
        repeat (5) begin
            @(negedge clk);
            if (raw_ready || busy || rgb_valid || done) fail("Idle consumed source without start");
        end
        start_valid = 1'b1;
        @(negedge clk);
        // Leave the command asserted: it must have no effect while busy.
        wait_count = 0;
        while (!(packed_valid && rgb_valid && !rgb_ready)) begin
            @(negedge clk);
            wait_count = wait_count + 1;
            if (wait_count > 100) fail("Could not reach pending integrated outputs");
        end
        if (!busy || !frame_error || start_ready) fail("Busy/error before reset incorrect");
        rst_n = 1'b0;
        start_valid = 1'b0;
        raw_valid = 1'b0;
        #1;
        if (busy || done || frame_error || rgb_valid || packed_valid || raw_ready)
            fail("Reset did not abandon integrated frame");
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        packed_ready = 1'b1;
        repeat (6) begin
            @(negedge clk);
            if (!start_ready || rgb_valid || packed_valid || done)
                fail("Ghost data/status after integrated reset");
        end
        checking = 1'b1;
        start_valid = 1'b1;
        @(negedge clk);
        start_valid = 1'b0;
        for (i = 0; i < 12; i = i + 1) begin
            raw_data = sources[i];
            raw_valid = 1'b1;
            raw_last = (i == 11);
            @(posedge clk);
            while (!raw_ready) @(posedge clk);
            @(negedge clk);
        end
        raw_valid = 1'b0;
        wait_count = 0;
        while (output_count < 4 || done_count < 1) begin
            @(negedge clk);
            wait_count = wait_count + 1;
            if (wait_count > 100) fail("Integrated restart timeout");
        end
        if (source_count != 12 || frame_error || done_count != 1)
            fail("Restart source/error/done status incorrect");
        repeat (5) @(negedge clk);

        // Reset buffered bytes before any complete word exists.
        reset_direct;
        for (i = 0; i < 4; i = i + 1) send_direct(24'habcdef, 1'b0);
        if (direct_out_valid) fail("Premature partial output without last");
        reset_direct;
        // Reset a stalled full word with a final 2-byte flush pending.
        direct_out_ready = 1'b0;
        for (i = 0; i < 6; i = i + 1) send_direct(24'habcdef, i == 5);
        if (!direct_out_valid || direct_out_last || direct_keep != 16'hffff)
            fail("Final overflow did not create full non-final word");
        reset_direct;
        // Reset a stalled final partial word.
        direct_out_ready = 1'b0;
        send_direct(24'habcdef, 1'b1);
        if (!direct_out_valid || !direct_out_last || direct_keep != 16'h0007)
            fail("Expected stalled final partial word");
        reset_direct;
        direct_checking = 1'b1;
        send_direct(24'h332211, 1'b1);
        repeat (8) @(negedge clk);
        if (direct_count != 1) fail("Direct restart did not produce exactly one word");
        $display("PASS tb_raw_reset integrated_pending carry full_flush partial_restart");
        $finish;
    end
    initial begin
        #100000;
        fail("Global timeout");
    end
endmodule
