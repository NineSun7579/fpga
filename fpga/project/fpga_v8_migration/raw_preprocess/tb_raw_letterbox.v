`timescale 1ns/1ps
// Direct 24-bit interface checks, including a stalled final padding pixel.
module tb_raw_letterbox;
    reg clk = 1'b0;
    always #5 clk = !clk;
    reg rst_n = 1'b0;
    reg start_valid = 1'b0;
    wire start_ready, busy, done, frame_error, config_error;
    reg [15:0] s_data = 16'd0;
    reg s_valid = 1'b0;
    reg s_last = 1'b0;
    wire s_ready;
    wire [23:0] m_data;
    wire m_valid, m_last;
    reg m_ready = 1'b0;
    reg [15:0] sources [0:11];
    reg [23:0] pixels [0:19];
    integer source_count = 0;
    integer pixel_count = 0;
    integer driven_index = -1;
    integer done_count = 0;
    integer hold_cycles = 0;
    integer stall_cycles = 0;
    integer cycles = 0;
    reg [23:0] held_data;
    reg held_last;
    reg stalled = 1'b0;
    reg final_fire;
    reg final_seen = 1'b0;
    reg checking = 1'b0;
    fpga_v8_raw_letterbox #(.WIDTH(4), .HEIGHT(3), .OUT_HEIGHT(5), .TOP_ROWS(1)) dut (
        .clk(clk), .rst_n(rst_n), .start_valid(start_valid), .start_ready(start_ready),
        .busy(busy), .done(done), .frame_error(frame_error), .config_error(config_error),
        .s_data(s_data), .s_valid(s_valid), .s_ready(s_ready), .s_last(s_last),
        .m_data(m_data), .m_valid(m_valid), .m_ready(m_ready), .m_last(m_last));
    task fail;
        input [511:0] reason;
        begin $display("FAIL letterbox cycle=%0d: %0s", cycles, reason); $finish; end
    endtask
    always @(negedge clk) begin
        if (rst_n && checking) begin
            if (source_count < 12) begin
                if (!s_valid || driven_index != source_count) begin
                    s_valid = (cycles % 5 != 0);
                    s_data = sources[source_count];
                    s_last = (source_count == 11);
                    driven_index = source_count;
                end
            end else begin
                // A marker arriving after the configured boundary must not
                // consume a surplus source word during bottom padding.
                s_valid = 1'b1;
                s_data = 16'hdead;
                s_last = 1'b1;
            end
            m_ready = (cycles % 4 != 0);
            if (m_valid && m_last && !final_seen) begin
                final_seen = 1'b1;
                hold_cycles = 9;
            end
            if (hold_cycles > 0) begin
                m_ready = 1'b0;
                hold_cycles = hold_cycles - 1;
            end
        end
    end
    always @(posedge clk) begin
        cycles = cycles + 1;
        if (rst_n && checking) begin
            final_fire = m_valid && m_ready && m_last;
            if (stalled && (!m_valid || m_data !== held_data || m_last !== held_last))
                fail("24-bit output changed while stalled");
            stalled = m_valid && !m_ready;
            held_data = m_data;
            held_last = m_last;
            if (s_valid && s_ready) begin
                if (source_count >= 12 || pixel_count + (m_valid && m_ready) < 4)
                    fail("RAW consumed outside body");
                source_count = source_count + 1;
            end
            if (m_valid && m_ready) begin
                if (pixel_count >= 20 || m_data !== pixels[pixel_count] ||
                    m_last != (pixel_count == 19)) fail("RGB/last differs from golden");
                pixel_count = pixel_count + 1;
            end
            if (m_valid && m_last && !m_ready) begin
                stall_cycles = stall_cycles + 1;
                if (!busy || done || start_ready || s_ready)
                    fail("Final padding stall did not retain busy/block inputs");
            end
            #1;
            if (done !== final_fire) fail("Done did not wait for final pixel handshake");
            if (done) done_count = done_count + 1;
            if (frame_error || config_error) fail("Unexpected error");
        end
    end
    initial begin
        $readmemh("source.hex", sources);
        $readmemh("pixels.hex", pixels);
        repeat (4) @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        start_valid = 1'b1;
        checking = 1'b1;
        @(negedge clk);
        start_valid = 1'b0;
        while (done_count == 0) @(negedge clk);
        if (source_count != 12 || pixel_count != 20 || stall_cycles < 9)
            fail("Count or final-stall coverage wrong");
        repeat (8) @(negedge clk);
        if (done_count != 1 || busy || m_valid || s_ready || !start_ready)
            fail("Ghost output/done or wrong idle status");
        $display("PASS tb_raw_letterbox final_pixel_stalls=%0d", stall_cycles);
        $finish;
    end
    initial begin #20000; fail("Timeout"); end
endmodule
