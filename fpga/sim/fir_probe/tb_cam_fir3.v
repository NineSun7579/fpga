`timescale 1ns / 1ps
// tb_cam_fir3: golden-model check of the hand-written 3-tap FIR.
// Expected output for each input beat = f(x[n], x[n-1], x[n-2]) computed at
// push time (unsigned per-channel (x+2x1+x2)>>2), delivered 1 cycle later.
module tb_cam_fir3;
    localparam CLK = 10;
    reg clk = 0, rst = 1;
    reg         i_valid = 0;
    reg  [15:0] i_pixel = 0;
    reg         i_vsync = 0;
    wire        o_valid;
    wire [15:0] o_pixel;
    wire        o_vsync;

    integer errors = 0, n_in = 0, n_out = 0;

    cam_fir3 u (.clk(clk), .rst(rst),
        .in_valid(i_valid), .in_pixel(i_pixel), .in_vsync(i_vsync),
        .out_valid(o_valid), .out_pixel(o_pixel), .out_vsync(o_vsync));

    always #(CLK/2) clk = ~clk;

    // FIFO of expected outputs (in order)
    reg [15:0] q_px [0:63];
    reg        q_v  [0:63];
    integer qh = 0, qt = 0;

    // golden taps
    reg [4:0] gr1 = 0, gr2 = 0, gb1 = 0, gb2 = 0;
    reg [5:0] gg1 = 0, gg2 = 0;

    function [15:0] fexp(input [15:0] d);
        reg [6:0] sr, sb; reg [7:0] sg;
        begin
            sr = {2'b0, d[15:11]} + {1'b0, gr1, 1'b0} + {2'b0, gr2};
            sg = {2'b0, d[10:5]}  + {1'b0, gg1, 1'b0} + {2'b0, gg2};
            sb = {2'b0, d[4:0]}   + {1'b0, gb1, 1'b0} + {2'b0, gb2};
            fexp = {sr[6:2], sg[7:2], sb[6:2]};
        end
    endfunction

    // DUT output checking: pop expected in order
    always @(posedge clk) begin
        if (o_valid) begin
            n_out = n_out + 1;
            if (qh == qt) begin
                errors = errors + 1;
                $display("UNEXPECTED output t=%0t got=%h", $time, o_pixel);
            end
            else begin
                if (o_pixel !== q_px[qh]) begin
                    errors = errors + 1;
                    $display("PIX MISMATCH t=%0t got=%h exp=%h", $time, o_pixel, q_px[qh]);
                end
                if (o_vsync !== q_v[qh]) begin
                    errors = errors + 1;
                    $display("VSYNC MISMATCH t=%0t got=%b exp=%b", $time, o_vsync, q_v[qh]);
                end
                qh = (qh + 1) % 64;
            end
        end
    end

    task push(input [15:0] d, input vs);
        begin
            @(negedge clk);
            i_valid = 1; i_pixel = d; i_vsync = vs;
            // expected value for THIS beat, computed with pre-shift taps
            q_px[qt] = fexp(d);
            q_v[qt]  = vs;
            qt = (qt + 1) % 64;
            n_in = n_in + 1;
            @(negedge clk);
            i_valid = 0; i_vsync = 0;
            // taps shift only on accepted beats (after the beat completes)
            gr2 = gr1; gr1 = d[15:11];
            gg2 = gg1; gg1 = d[10:5];
            gb2 = gb1; gb1 = d[4:0];
        end
    endtask

    integer k;
    initial begin
        repeat (3) @(negedge clk);
        rst = 0;
        repeat (2) @(negedge clk);

        // T1: constant gray incl. G=32 sign boundary -> steady state == input
        for (k = 0; k < 10; k = k + 1) push(16'h8410, 1'b0);
        // T2: ramp full-range
        for (k = 0; k < 20; k = k + 1) push({k[4:0], k[5:0], k[4:0]}, 1'b0);
        // T3: gaps between beats
        push(16'hFFFF, 1'b0); repeat (5) @(negedge clk);
        push(16'h0000, 1'b0); repeat (20) @(negedge clk);
        push(16'hA5A5, 1'b0);
        // T4: vsync-marked beat
        push(16'h1234, 1'b1);
        // T5: constant again (taps must have shifted correctly through gaps)
        for (k = 0; k < 8; k = k + 1) push(16'h8410, 1'b0);

        repeat (10) @(negedge clk);
        $display("DONE n_in=%0d n_out=%0d errors=%0d", n_in, n_out, errors);
        if (errors == 0 && n_in == n_out) $display("CAMFIR3_PASS");
        else $display("CAMFIR3_FAIL");
        $finish;
    end
endmodule
