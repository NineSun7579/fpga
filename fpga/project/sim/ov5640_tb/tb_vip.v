`timescale 1ns/1ps

module tb_vip;
    localparam integer W = 8;
    localparam integer H = 4;
    localparam integer S = 8;

    reg         clk;
    reg         rst;
    reg         in_valid;
    reg [15:0]  in_pixel;
    reg         in_vsync;
    wire        out_valid;
    wire [15:0] out_pixel;
    wire        out_vsync;
    wire        bp_valid;
    wire [15:0] bp_pixel;
    wire        bp_vsync;

    integer out_count;
    integer frame_pulses;
    integer changed_pixels;
    integer errors;
    integer frame_id;
    integer pix_id;

    vip #(
        .W(W), .H(H), .STRIDE(S), .AW(3), .GAP_LEN(4)
    ) dut (
        .clk(clk), .rst(rst),
        .en(1'b1), .strength(3'd2),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .out_valid(out_valid), .out_pixel(out_pixel), .out_vsync(out_vsync)
    );

    vip #(
        .W(W), .H(H), .STRIDE(S), .AW(3), .GAP_LEN(4)
    ) dut_bypass (
        .clk(clk), .rst(rst),
        .en(1'b0), .strength(3'd2),
        .in_valid(in_valid), .in_pixel(in_pixel), .in_vsync(in_vsync),
        .out_valid(bp_valid), .out_pixel(bp_pixel), .out_vsync(bp_vsync)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (!rst) begin
            if (out_valid) begin
                out_count = out_count + 1;
                if (out_pixel != bp_pixel)
                    changed_pixels = changed_pixels + 1;
                if (^out_pixel === 1'bx) begin
                    $display("VIP_TB_FAIL X pixel at output %0d", out_count);
                    errors = errors + 1;
                end
            end
            if (out_valid != bp_valid || out_vsync != bp_vsync) begin
                    $display("VIP_TB_FAIL median/bypass timing mismatch");
                errors = errors + 1;
            end
            if (out_vsync) begin
                frame_pulses = frame_pulses + 1;
            end
        end
    end

    task send_frame;
        input integer f;
        integer i;
        begin
            // Sensor vertical blanking and frame-start pulse.
            @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
            repeat (3) @(negedge clk);
            in_vsync = 1'b0;
            for (i = 0; i < W*H; i = i + 1) begin
                @(negedge clk);
                in_valid = 1'b1;
                in_pixel = ((f*W*H+i) * 16'h031d) ^ 16'h5a37;
            end
            @(negedge clk); in_valid = 1'b0; in_pixel = 16'd0;
            repeat (6) @(negedge clk);
        end
    endtask

    initial begin
        rst = 1'b1;
        in_valid = 1'b0;
        in_pixel = 16'd0;
        in_vsync = 1'b0;
        out_count = 0;
        frame_pulses = 0;
        changed_pixels = 0;
        errors = 0;

        repeat (5) @(negedge clk);
        rst = 1'b0;

        // Three input frames produce two complete, frame-locked output frames:
        // the first frame is intentionally primed because the line buffers are
        // empty after reset.
        send_frame(0);
        send_frame(1);
        send_frame(2);
        // The pipeline emits the last pending column on the next frame-start
        // opportunity.  Provide that blanking pulse without accepting data.
        @(negedge clk); in_valid = 1'b0; in_vsync = 1'b1;
        repeat (3) @(negedge clk);
        in_vsync = 1'b0;
        @(negedge clk); in_valid = 1'b1; in_pixel = 16'h0000;
        @(negedge clk); in_valid = 1'b0;
        repeat (80) @(negedge clk);

        if (out_count != 88) begin
            $display("VIP_TB_FAIL output count=%0d expected=88", out_count);
            errors = errors + 1;
        end
        if (frame_pulses != 2) begin
            $display("VIP_TB_FAIL frame pulses=%0d expected=2", frame_pulses);
            errors = errors + 1;
        end
        if (changed_pixels == 0) begin
            $display("VIP_TB_FAIL median filter did not change any pixel");
            errors = errors + 1;
        end
        if (errors == 0)
            $display("VIP_TB_PASS outputs=%0d frame_pulses=%0d changed=%0d", out_count, frame_pulses, changed_pixels);
        else
            $display("VIP_TB_FAIL errors=%0d outputs=%0d frame_pulses=%0d changed=%0d", errors, out_count, frame_pulses, changed_pixels);
        $finish;
    end
endmodule
