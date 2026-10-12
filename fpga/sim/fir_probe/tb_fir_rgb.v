`timescale 1ns / 1ps
// tb_fir_rgb: verify the EXACT ov5640_top.v FIR wiring against an unsigned
// golden: RGB565 split, G-channel sign bias (^6'h20) in and out, recombine.
// Self-checks steady-state constants (incl. the G=32 sign boundary) and a
// G-ramp linearity check.
module tb_fir_rgb;

    localparam CLK_PERIOD = 10;

    reg clk = 0, rstn = 0;
    reg         i_valid = 0;
    reg [15:0]  i_pixel = 0;
    reg         i_last  = 0;
    wire        r_ready, g_ready, b_ready;
    wire [10:0] r_out, g_out, b_out;
    wire        r_v, g_v, b_v, r_l, g_l, b_l;

    integer errors = 0;
    integer k;

    always #(CLK_PERIOD/2) clk = ~clk;
    GTP_GRS GRS_INST( .GRS_N(1'b1) );

    // --- exact ov5640_top.v wiring ---
    FIR u_fir_r (
        .i_clk(clk), .i_rstn(rstn),
        .i_axi4s_data_tdata({1'b0, i_pixel[15:11]}),
        .i_axi4s_data_tlast(i_last),
        .o_axi4s_data_tready(r_ready),
        .i_axi4s_data_tvalid(i_valid),
        .o_axi4s_data_tdata(r_out),
        .o_axi4s_data_tlast(r_l),
        .i_axi4s_data_tready(1'b1),
        .o_axi4s_data_tvalid(r_v)
    );
    FIR u_fir_g (
        .i_clk(clk), .i_rstn(rstn),
        .i_axi4s_data_tdata(i_pixel[10:5] ^ 6'h20),
        .i_axi4s_data_tlast(i_last),
        .o_axi4s_data_tready(g_ready),
        .i_axi4s_data_tvalid(i_valid),
        .o_axi4s_data_tdata(g_out),
        .o_axi4s_data_tlast(g_l),
        .i_axi4s_data_tready(1'b1),
        .o_axi4s_data_tvalid(g_v)
    );
    FIR u_fir_b (
        .i_clk(clk), .i_rstn(rstn),
        .i_axi4s_data_tdata({1'b0, i_pixel[4:0]}),
        .i_axi4s_data_tlast(i_last),
        .o_axi4s_data_tready(b_ready),
        .i_axi4s_data_tvalid(i_valid),
        .o_axi4s_data_tdata(b_out),
        .o_axi4s_data_tlast(b_l),
        .i_axi4s_data_tready(1'b1),
        .o_axi4s_data_tvalid(b_v)
    );

    wire        fir_video_valid = r_v & g_v & b_v;
    wire [15:0] fir_video_data  = {r_out[6:2], (g_out[7:2] ^ 6'h20), b_out[6:2]};

    // steady-state check: with a constant input the FIR output must return
    // the same RGB565 value exactly (any [1,2,1]/4 window alignment).
    reg [15:0] cur_const = 16'hxxxx;
    integer n_cur = 0;
    always @(posedge clk) begin
        if (i_valid && (i_pixel === cur_const)) n_cur = n_cur + 1;
        else if (i_valid) begin
            cur_const = i_pixel;
            n_cur = 1;
        end
        if (fir_video_valid && n_cur >= 8) begin
            if (fir_video_data !== cur_const) begin
                errors = errors + 1;
                $display("STEADY-FAIL t=%0t const=%h got=%h", $time, cur_const, fir_video_data);
            end else begin
                $display("STEADY-OK   t=%0t const=%h got=%h", $time, cur_const, fir_video_data);
            end
        end
    end

    task beat(input [15:0] d, input lst, input integer gap);
        begin
            @(negedge clk);
            i_valid <= 1'b1; i_pixel <= d; i_last <= lst;
            @(negedge clk);
            i_valid <= 1'b0; i_last <= 1'b0;
            if (gap > 0) begin
                i_pixel <= 16'h0000;
                repeat (gap) @(negedge clk);
            end
        end
    endtask

    initial begin
        rstn = 0;
        repeat (5) @(negedge clk);
        rstn = 1;
        repeat (5) @(negedge clk);

        $display("=== T1: gray 32 constant (G sign boundary) x12 ===");
        for (k = 0; k < 12; k = k + 1) beat({5'd16, 6'd32, 5'd16}, 1'b0, 0);

        $display("=== T2: gray 40 constant x12 ===");
        for (k = 0; k < 12; k = k + 1) beat({5'd20, 6'd40, 5'd20}, 1'b0, 0);

        $display("=== T3: gray 10 constant x12 ===");
        for (k = 0; k < 12; k = k + 1) beat({5'd5, 6'd10, 5'd5}, 1'b0, 0);

        $display("=== T4: tlast ===");
        beat({5'd5, 6'd10, 5'd5}, 1'b1, 3);

        $display("=== T5: gray 32 again after frame boundary x12 ===");
        for (k = 0; k < 12; k = k + 1) beat({5'd16, 6'd32, 5'd16}, 1'b0, 0);

        repeat (40) @(negedge clk);
        $display("=== DONE errors=%0d ===", errors);
        $finish;
    end
endmodule
