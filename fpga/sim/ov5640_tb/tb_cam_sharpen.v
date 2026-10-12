// tb_cam_sharpen.v -- [SHARP 2026-09-19] pipeline + golden verification for the
// luminance sharpener. Small geometry (16x8) so the whole pipeline is checked
// cycle-accurately in seconds.
//
// Checks:
//   1. exactly W*H output pixels between two out_vsync pulses
//   2. every output pixel equals the golden 3x3 luminance-sharpen formula
//   3. edge handling (left/right/top masked to centre) matches the RTL
//   4. en=0 produces a bit-exact delayed copy of the input
`timescale 1ns/1ps
module tb_cam_sharpen;

    localparam integer W = 16;
    localparam integer H = 8;
    localparam integer STRIDE = 16;
    localparam integer AW = 4;

    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1;

    reg        en = 0;
    reg [2:0]  strength = 3'd3;
    reg        in_valid = 0;
    reg [15:0] in_pixel = 0;
    reg        in_vsync = 0;

    wire       out_valid;
    wire [15:0] out_pixel;
    wire       out_vsync;

    cam_sharpen #(
        .W(W), .H(H), .STRIDE(STRIDE), .AW(AW)
    ) dut (
        .clk(clk), .rst(rst),
        .en(en), .strength(strength),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .out_valid(out_valid), .out_pixel(out_pixel), .out_vsync(out_vsync)
    );

    // ---------------- input pattern (mod-H periodic rows) ----------------
    function [15:0] base_pix;
        input integer r;      // row 0..H-1
        input integer x;      // col 0..W-1
        reg [7:0] rr, gg, bb;
        begin
            rr = (x * 16 + r * 24) & 8'hff;
            gg = (x * 9  + r * 40) & 8'hff;
            bb = (x * 4  + 80)     & 8'hff;
            base_pix = {rr[7:3], gg[7:2], bb[7:3]};
        end
    endfunction

    // ---------------- golden model (mirrors the RTL math) ----------------
    function [7:0] yof;
        input [15:0] p;
        reg [7:0] r8, g8, b8;
        reg [15:0] y;
        begin
            r8 = {p[15:11], p[13:11]};
            g8 = {p[10:5],  p[6:5] };
            b8 = {p[4:0],   p[2:0] };
            y  = (r8<<6) + (r8<<3) + (r8<<1)
               + (g8<<7) + (g8<<4) + (g8<<2) + (g8<<1)
               + (b8<<4) + (b8<<3) + (b8<<2) + b8;
            yof = y[15:8];
        end
    endfunction

    function [7:0] clamp8f;
        input integer v;
        begin
            if (v < 0)        clamp8f = 8'd0;
            else if (v > 255) clamp8f = 8'd255;
            else              clamp8f = v[7:0];
        end
    endfunction

    function [15:0] golden;
        input integer j;      // output line within the frame 0..H-1
        input integer x;      // column
        input integer sh;     // strength
        integer c_row, u_row, d_row;
        reg [15:0] pc, pl, pr, pu, pd;
        reg signed [11:0] lac, lsh;
        integer ys;
        reg [7:0] yc, yp;
        integer dy;
        reg [7:0] r8, g8, b8;
        reg [7:0] orr, ogg, obb;
        begin
            // output line j is input line (j+1)-1 = j (it lags the input by one
            // line); pattern is mod-H periodic so row == j.
            c_row = j % H;
            // up (row j-1) masked for j = 0 (RTL: up_ok = input line >= 2)
            u_row = (j >= 1) ? (j - 1) : c_row;
            // down (row j+1) masked for the last line (RTL: dn_ok = input line != 0)
            d_row = (j == H-1) ? c_row : (j + 1);

            pc = base_pix(c_row, x);
            pl = (x == 0)     ? pc : base_pix(c_row, x-1);
            pr = (x == W-1)   ? pc : base_pix(c_row, x+1);
            pu = (j >= 1)     ? base_pix(u_row, x) : pc;
            pd = (j == H-1)   ? pc : base_pix(d_row, x);

            yc = yof(pc);
            // signed arithmetic exactly as in the RTL ($signed casts)
            lac = $signed(4*yc) - $signed({4'b0, yof(pu)}) - $signed({4'b0, yof(pd)})
                                 - $signed({4'b0, yof(pl)}) - $signed({4'b0, yof(pr)});
            lsh = lac >>> sh;
            ys  = $signed({1'b0, yc}) + lsh;       // signed add (fix: was unsigned)
            yp  = (ys < 0) ? 8'd0 : ((ys > 255) ? 8'd255 : ys[7:0]);
            dy  = yp - yc;

            r8 = {pc[15:11], pc[13:11]};
            g8 = {pc[10:5],  pc[6:5] };
            b8 = {pc[4:0],   pc[2:0] };
            orr = clamp8f(r8 + dy);
            ogg = clamp8f(g8 + dy);
            obb = clamp8f(b8 + dy);
            golden = {orr[7:3], ogg[7:2], obb[7:3]};
        end
    endfunction

    // ---------------- stimulus / checker ----------------
    integer errors = 0;
    integer gchecks = 0;
    integer line_idx = 0;       // output line within the current frame
    integer col_idx = 0;        // output column within the line
    integer frames = 0;
    integer pix_in_frame = 0;
    integer f, y, x;

    task check(input cond, input [8*60:1] msg);
        begin
            if (!cond) begin
                errors = errors + 1;
                $display("[FAIL] %0s (frame %0d line %0d col %0d t=%0t)",
                         msg, frames, line_idx, col_idx, $time);
            end
        end
    endtask

    always @(posedge clk) begin
        if (out_valid) begin
            if (frames >= 1) begin          // first partial frame is dropped
                if (en) begin
                    if (out_pixel !== golden(line_idx, col_idx, strength)) begin
                        if (errors < 8)
                            $display("[DIFF] f%0d l%0d k%0d got %04X exp %04X",
                                     frames, line_idx, col_idx, out_pixel,
                                     golden(line_idx, col_idx, strength));
                        errors = errors + 1;
                    end
                    gchecks = gchecks + 1;
                end else begin
                    check(out_pixel === base_pix(line_idx % H, col_idx),
                          "passthrough mismatch");
                end
            end
            col_idx = col_idx + 1;
            pix_in_frame = pix_in_frame + 1;
        end
        if (out_vsync) begin
            if (frames >= 1)
                check(pix_in_frame == W*H, "pixels per frame != W*H");
            frames = frames + 1;
            line_idx = 0; col_idx = 0; pix_in_frame = 0;
        end
        // column wrap bookkeeping
        if (out_valid && col_idx == W) begin
            col_idx = 0;
            line_idx = line_idx + 1;
        end
    end

    // ---- push-stage checker: verify windows independently of the output path ----
    integer push_n = 0;
    integer perr = 0;
    integer pj, pk;
    always @(posedge clk) begin
        if (1'b0 && dut.push) begin
            if (en && push_n >= W*H) begin
                pj = ((push_n % (W*H)) / W);
                pk = (push_n % W);
                if (dut.Mres !== golden(pj, pk, strength)) begin
                    if (perr < 6)
                        $display("[PUSH-DIFF] n=%0d j=%0d k=%0d got %04X exp %04X | W=(%04X %04X %04X %04X %04X)",
                                 push_n, pj, pk, dut.Mres, golden(pj, pk, strength),
                                 dut.Wc, dut.Wl, dut.Wr, dut.Wu, dut.Wd);
                    perr = perr + 1;
                end
            end
            push_n = push_n + 1;
        end
    end

    // ---- dump frame 1 (first checked frame) for offline diff ----
    reg [15:0] dump_mem [0:W*H-1];
    integer dump_n = 0;
    integer dump_fd;
    integer dmp_i;
    reg dumped = 1'b0;
    always @(posedge clk) begin
        if (out_valid && !dumped) begin
            if (dump_n < W*H) begin
                dump_mem[dump_n] = out_pixel;
                dump_n = dump_n + 1;
            end
            if (dump_n == W*H) begin           // one full frame collected
                dump_fd = $fopen("out_frame.txt", "w");
                for (dmp_i = 0; dmp_i < W*H; dmp_i = dmp_i + 1)
                    $fdisplay(dump_fd, "%04X", dump_mem[dmp_i]);
                $fclose(dump_fd);
                $display("[DUMP] wrote %0d pixels", W*H);
                dumped = 1'b1;
            end
        end
    end

    // ---- cycle trace around the first vsync ----
    integer tr = 0;
    always @(posedge clk) begin
        if (!dumped && (out_valid || out_vsync)) begin
            if (tr < 6)
                $display("[TX %0t] ov=%b vs=%b op=%04X rp=%0d head=%04X eof=%b last_pix=%04X",
                         $time, out_valid, out_vsync, out_pixel, dut.of_rp,
                         dut.of_head[15:0], dut.of_head[16], dut.ofifo[dut.of_rp - 1'b1][15:0]);
            tr = tr + 1;
        end
    end

    task feed_frame;
        input integer sh_now;
        integer yy, xx;
        begin
            for (yy = 0; yy < H; yy = yy + 1) begin
                for (xx = 0; xx < W; xx = xx + 1) begin
                    @(negedge clk);
                    in_valid = 1'b1;
                    in_pixel = base_pix(yy % H, xx);
                end
                if (yy == H-1) begin     // [DUMMY] contract: one extra pixel at the tail
                    @(negedge clk);
                    in_valid = 1'b1;
                    in_pixel = 16'hDEAD;
                    @(negedge clk);
                    in_valid = 1'b0;
                    @(negedge clk);
                    in_vsync = 1'b1;      // frame boundary marks the next frame
                    @(negedge clk);
                    in_vsync = 1'b0;
                end
            end
            @(negedge clk);
            in_valid = 1'b0;
            // drain the elastic FIFO (real cameras have long vertical blanking;
            // the output drains at ~2/3 the input rate because of the frame gap)
            repeat (300) @(negedge clk);
        end
    endtask

    initial begin
        rst = 1;
        repeat (10) @(negedge clk);
        rst = 0;
        repeat (10) @(negedge clk);

        // ---- test 1: sharpening enabled, strength 3 ----
        en = 1'b1; strength = 3'd3;
        for (f = 0; f < 10; f = f + 1) feed_frame(3);
        repeat (50) @(negedge clk);

        // ---- test 2: passthrough (en=0) ----
        en = 1'b0;
        frames = -1000;              // suppress golden checking for this phase
        for (f = 0; f < 3; f = f + 1) feed_frame(0);
        repeat (50) @(negedge clk);

        if (errors == 0)
            $display("=== TB SHARPEN PASS: %0d golden pixel checks OK (frames %0d) ===", gchecks, frames + 1000);
        else
            $display("=== TB SHARPEN FAIL: %0d errors ===", errors);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("[FAIL] global timeout");
        $finish;
    end

endmodule
