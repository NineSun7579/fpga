`timescale 1ns/1ps
// Count vip output pixels per frame at full 640x480 to prove the write engine
// will always see exactly W*H pixels between vsync pulses.
module tb_vip_cnt;
    localparam integer W = 640;
    localparam integer H = 480;
    localparam integer S = 1024;
    localparam integer AW = 10;

    reg         clk;
    reg         rst;
    reg         in_valid;
    reg  [15:0] in_pixel;
    reg         in_vsync;
    wire        out_valid;
    wire [15:0] out_pixel;
    wire        out_vsync;

    integer cyc;
    integer out_pix;
    integer frame_no;
    integer bad_frames;
    integer i;
    integer f;

    vip #(.W(W), .H(H), .STRIDE(S), .AW(AW), .GAP_LEN(8)) dut (
        .clk(clk), .rst(rst),
        .en(1'b1), .strength(3'd0),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .out_valid(out_valid), .out_pixel(out_pixel), .out_vsync(out_vsync)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Count output pixels between vsync pulses.
    always @(posedge clk) begin
        if (!rst) begin
            if (out_valid) out_pix = out_pix + 1;
            if (out_vsync) begin
                frame_no = frame_no + 1;
                $display("VIPCNT frame %0d: pixels=%0d (expect %0d)", frame_no, out_pix, W*H);
                if (out_pix != W*H) bad_frames = bad_frames + 1;
                out_pix = 0;
            end
        end
    end

    task send_frame;
        input integer fid;
        begin
            @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
            repeat (4) @(negedge clk);
            in_vsync = 1'b0;
            for (i = 0; i < W*H; i = i + 1) begin
                @(negedge clk);
                in_valid = 1'b1;
                in_pixel = (i + fid*7) & 16'hFFFF;
            end
            @(negedge clk); in_valid = 1'b0;
            repeat (4) @(negedge clk);
        end
    endtask

    initial begin
        rst = 1'b1; in_valid = 1'b0; in_pixel = 16'd0; in_vsync = 1'b0;
        cyc = 0; out_pix = 0; frame_no = 0; bad_frames = 0;
        repeat (5) @(negedge clk);
        rst = 1'b0;

        for (f = 0; f < 3; f = f + 1) send_frame(f);

        // Provide trailing blanking + pixel so the last flush can drain.
        @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
        repeat (4) @(negedge clk);
        in_vsync = 1'b0;
        @(negedge clk); in_valid = 1'b1; in_pixel = 16'h0000;
        @(negedge clk); in_valid = 1'b0;
        repeat (200) @(negedge clk);

        if (bad_frames == 0 && frame_no == 2)
            $display("VIPCNT_PASS frames=%0d all W*H=%0d", frame_no, W*H);
        else
            $display("VIPCNT_FAIL frames=%0d bad=%0d", frame_no, bad_frames);
        $finish;
    end
endmodule
