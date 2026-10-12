`timescale 1ns/1ps
module tb_rgb888_pack128;
    parameter integer INPUTS = 561;
    parameter integer WORDS = 121;
    reg clk = 1'b0;
    always #5 clk = !clk;
    reg rst_n = 1'b0;
    reg [23:0] s_data = 24'd0;
    reg s_valid = 1'b0;
    wire s_ready;
    reg s_last = 1'b0;
    wire [127:0] m_data;
    wire [15:0] m_keep;
    wire m_valid, m_last;
    reg m_ready = 1'b0;
    reg [23:0] inputs [0:INPUTS-1];
    reg input_last [0:INPUTS-1];
    reg [127:0] words [0:WORDS-1];
    reg [15:0] keeps [0:WORDS-1];
    reg word_last [0:WORDS-1];
    integer input_count = 0;
    integer output_count = 0;
    integer driven_index = -1;
    integer cycles = 0;
    integer final_words = 0;
    integer stalls = 0;
    integer output_file;
    integer timeout_count;
    reg [31:0] rng = 32'ha513794b;
    reg stalled = 1'b0;
    reg [127:0] held_data;
    reg [15:0] held_keep;
    reg held_last;
    fpga_v8_rgb888_pack128 dut (
        .clk(clk), .rst_n(rst_n), .s_data(s_data), .s_valid(s_valid),
        .s_ready(s_ready), .s_last(s_last), .m_data(m_data), .m_keep(m_keep),
        .m_valid(m_valid), .m_ready(m_ready), .m_last(m_last));
    task fail;
        input [511:0] reason;
        begin
            $display("FAIL packer cycle=%0d input=%0d output=%0d: %0s",
                     cycles, input_count, output_count, reason);
            $finish;
        end
    endtask
    always @(negedge clk) begin
        if (rst_n) begin
            rng = (rng ^ (rng << 13));
            rng = (rng ^ (rng >> 17));
            rng = (rng ^ (rng << 5));
            if (input_count < INPUTS) begin
                if (!s_valid || driven_index != input_count) begin
                    s_valid = rng[3:0] > 3;
                    s_data = inputs[input_count];
                    s_last = input_last[input_count];
                    driven_index = input_count;
                end
            end else begin
                s_valid = 1'b0;
                s_data = rng[23:0];
                s_last = rng[20];
            end
            m_ready = rng[7:4] > 6;
        end
    end
    always @(posedge clk) begin
        cycles = cycles + 1;
        if (rst_n) begin
            if (stalled && (!m_valid || m_data !== held_data ||
                            m_keep !== held_keep || m_last !== held_last))
                fail("Output changed while stalled");
            stalled = m_valid && !m_ready;
            held_data = m_data;
            held_keep = m_keep;
            held_last = m_last;
            if (s_valid && s_ready) input_count = input_count + 1;
            if (m_valid && !m_ready) stalls = stalls + 1;
            if (m_valid && m_ready) begin
                if (output_count >= WORDS) fail("Ghost output word");
                if (m_data !== words[output_count] || m_keep !== keeps[output_count] ||
                    m_last !== word_last[output_count])
                    fail("Data, keep or last differs from Python golden");
                $fwrite(output_file, "%032h %04h %0d %0d\n", m_data,
                        m_keep, m_last, cycles);
                output_count = output_count + 1;
                if (m_last) final_words = final_words + 1;
            end
        end else stalled = 1'b0;
    end
    initial begin
        $readmemh("source24.hex", inputs);
        $readmemh("source_last.hex", input_last);
        $readmemh("words.hex", words);
        $readmemh("keeps.hex", keeps);
        $readmemh("word_last.hex", word_last);
        output_file = $fopen("actual_words.txt", "w");
        repeat (4) @(negedge clk);
        rst_n = 1'b1;
        timeout_count = 0;
        while (output_count < WORDS) begin
            @(negedge clk);
            timeout_count = timeout_count + 1;
            if (timeout_count > INPUTS*20 + 500) fail("Timeout");
        end
        if (input_count != INPUTS || final_words != 33) fail("Frame/input count wrong");
        repeat (20) @(negedge clk);
        $fclose(output_file);
        $display("PASS tb_rgb888_pack128 cycles=%0d stalls=%0d frames=%0d",
                 cycles, stalls, final_words);
        $finish;
    end
endmodule
