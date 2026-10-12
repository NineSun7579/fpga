`timescale 1ns/1ps
module tb_display_scaler;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg [15:0] s_pixel = 0;
    reg s_valid = 0;
    wire s_ready;
    wire [15:0] m_pixel;
    wire m_valid, m_sof, m_eof;
    reg m_ready = 0;
    rgb565_display_decimator dut(.*);

    reg [15:0] stimulus [0:921599];
    reg capture = 0;
    integer fd, outputs = 0, bubbles = 0, stalls = 0;
    reg held = 0;
    reg [17:0] previous;
    reg [31:0] rng = 32'hcf314159;
    integer accepted, cycles, frame_id, i;
    reg last_fire = 0;

    function [31:0] next_rng(input [31:0] a);
        reg [31:0] b;
        begin
            b = a ^ (a << 13);
            b = b ^ (b >> 17);
            next_rng = b ^ (b << 5);
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n) held = 0;
        else begin
            if (held && (!m_valid || {m_sof,m_eof,m_pixel} !== previous))
                $fatal(1, "Output changed while stalled");
            held = m_valid && !m_ready;
            previous = {m_sof,m_eof,m_pixel};
            if (capture) begin
                if (s_valid && !s_ready) stalls = stalls + 1;
                if (!s_valid) bubbles = bubbles + 1;
                if (m_valid && m_ready) begin
                    $fwrite(fd, "%04x %0d %0d\n", m_pixel, m_sof, m_eof);
                    outputs = outputs + 1;
                end
            end
        end
    end

    task reset_stream;
        begin
            @(negedge clk);
            rst_n = 0; s_valid = 0; m_ready = 0;
            #1;
            if (m_valid !== 0 || s_ready !== 0 || m_sof !== 0 || m_eof !== 0)
                $fatal(1, "Reset failed to clear pending output/tags");
            repeat (3) @(negedge clk);
            rst_n = 1;
        end
    endtask

    // Abort a frame with a pending selected output and reset its coordinates.
    task abort_stalled(input integer beats);
        integer n;
        begin
            n = 0;
            while (n < beats) begin
                @(negedge clk);
                s_valid = 1; s_pixel = n ^ 16'hdead; m_ready = 1;
                @(posedge clk);
                if (s_ready) n = n + 1;
            end
            @(negedge clk); s_valid = 0; m_ready = 0;
            repeat (12) @(negedge clk);
            if (!m_valid) $fatal(1, "Reset test did not leave a stalled pixel");
            reset_stream();
        end
    endtask

    initial begin
        $readmemh("stimulus.hex", stimulus);
        fd = $fopen("actual.txt", "w");
        if (!fd) $fatal(1, "Cannot open actual.txt");
        reset_stream();
        abort_stalled(1);
        abort_stalled(1283); // (2,2), partway through frame
        capture = 1;
        accepted = 0; cycles = 0;
        while (accepted < 921600) begin
            @(negedge clk);
            rng = next_rng(rng);
            frame_id = accepted / 307200;
            if (last_fire) s_valid = 0;
            // Keep input valid and payload unchanged until the handshake.
            if (!s_valid) begin
                s_valid = (frame_id == 0) || (rng[3:0] != 0);
                s_pixel = stimulus[accepted];
            end
            if (frame_id == 0) m_ready = 1;
            else if (frame_id == 1) m_ready = rng[4] || rng[8];
            else m_ready = ((cycles % 257) >= 97) && rng[7];
            @(posedge clk);
            last_fire = s_valid && s_ready;
            if (last_fire) begin
                accepted = accepted + 1;
            end
            cycles = cycles + 1;
        end
        @(negedge clk); s_valid = 0; m_ready = 1;
        repeat (8) @(negedge clk);
        if (outputs != 230400 || stalls == 0 || bubbles == 0)
            $fatal(1, "Counts failed outputs=%0d stalls=%0d bubbles=%0d", outputs, stalls, bubbles);
        if (m_valid) $fatal(1, "Unexpected residual output");
        $fclose(fd);
        $display("PASS RTL: accepted=%0d outputs=%0d stalls=%0d bubbles=%0d; two stalled resets", accepted, outputs, stalls, bubbles);
        $finish;
    end

    initial begin
        #100000000;
        $fatal(1, "Watchdog timeout");
    end
endmodule
