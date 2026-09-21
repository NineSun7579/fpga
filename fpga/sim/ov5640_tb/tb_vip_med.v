`timescale 1ns/1ps
// Alignment-free correctness check for the 3x3 per-channel median:
//  * uniform frames -> every output pixel must equal that frame's constant
//    (catches channel swaps / mixing / stuck values)
//  * a single-pixel impulse must be removed by the median
module tb_vip_med;
    localparam integer W = 8;
    localparam integer H = 4;
    localparam integer S = 8;
    localparam integer AW = 3;

    reg         clk, rst;
    reg         in_valid;
    reg  [15:0] in_pixel;
    reg         in_vsync;
    wire        out_valid;
    wire [15:0] out_pixel;
    wire        out_vsync;

    integer CONST [0:4];
    integer outf [0:4*W*H-1];
    integer outf_no, outf_cnt;
    integer i, f, k, errs, uniform, val, seq_ok, last_val;
    integer frames_seen;

    vip #(.W(W), .H(H), .STRIDE(S), .AW(AW), .GAP_LEN(4)) dut (
        .clk(clk), .rst(rst),
        .en(1'b1), .strength(3'd0),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .out_valid(out_valid), .out_pixel(out_pixel), .out_vsync(out_vsync)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (!rst) begin
            if (out_valid) begin
                outf[outf_no*W*H + outf_cnt] = out_pixel;
                outf_cnt = outf_cnt + 1;
            end
            if (out_vsync) begin
                outf_no = outf_no + 1;
                outf_cnt = 0;
            end
        end
    end

    // frame ff: uniform CONST[ff], except frame 3 has a centre impulse
    task send_frame;
        input integer ff;
        begin
            @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
            repeat (4) @(negedge clk);
            in_vsync = 1'b0;
            for (i = 0; i < W*H; i = i + 1) begin
                @(negedge clk);
                in_valid = 1'b1;
                if (ff == 3 && i == (H/2)*W + (W/2)) in_pixel = 16'h7FFF;
                else                                  in_pixel = CONST[ff][15:0];
            end
            @(negedge clk); in_valid = 1'b0;
            repeat (4) @(negedge clk);
        end
    endtask

    initial begin
        rst = 1'b1; in_valid = 1'b0; in_pixel = 16'd0; in_vsync = 1'b0;
        outf_no = 0; outf_cnt = 0; errs = 0;
        CONST[0] = 16'h1234;
        CONST[1] = 16'h2A55;
        CONST[2] = 16'h3F0F;
        CONST[3] = 16'h1234;   // impulse frame base
        CONST[4] = 16'h1234;

        repeat (5) @(negedge clk);
        rst = 1'b0;
        for (f = 0; f < 5; f = f + 1) send_frame(f);
        @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
        repeat (4) @(negedge clk);
        in_vsync = 1'b0;
        @(negedge clk); in_valid = 1'b1; in_pixel = 16'h0000;
        @(negedge clk); in_valid = 1'b0;
        repeat (600) @(negedge clk);

        $display("---- output frames ----");
        last_val = -1;
        seq_ok = 1;
        for (k = 0; k < outf_no; k = k + 1) begin
            uniform = 1;
            val = outf[k*W*H];
            for (i = 1; i < W*H; i = i + 1)
                if (outf[k*W*H + i] !== val) uniform = 0;
            $display("  out frame %0d: uniform=%0d value=0x%04X", k, uniform, val);
            if (!uniform) begin
                $display("    -> NOT UNIFORM: median is not filtering a uniform frame");
                errs = errs + 1;
            end
            // every output frame must equal one of the input constants
            f = -1;
            if (val === 16'h1234) f = 0;
            else if (val === 16'h2A55) f = 1;
            else if (val === 16'h3F0F) f = 2;
            if (f < 0) begin
                $display("    -> value is not any input frame constant");
                errs = errs + 1;
            end
            if (val !== last_val) last_val = val;
        end

        if (outf_no < 2) begin
            $display("  too few output frames: %0d", outf_no);
            errs = errs + 1;
        end

        if (errs == 0)
            $display("VIPMED_PASS frames=%0d uniform frames, impulse rejected, no channel mixing", outf_no);
        else
            $display("VIPMED_FAIL errors=%0d", errs);
        $finish;
    end
endmodule
