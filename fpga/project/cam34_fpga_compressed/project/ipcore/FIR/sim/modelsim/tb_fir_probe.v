`timescale 1ns / 1ps
// tb_fir_probe: characterize the Pango FIR IP exactly as ov5640_top.v drives it
// (6-bit tdata, tlast=frame marker, input tready tied 1).  Goals:
//   1. in/out beat count 1:1?         2. latency in cycles
//   3. output arithmetic semantics (signed vs unsigned, sum vs sum/4)
//   4. behaviour across valid gaps (camera blanking)
module tb_fir_probe;

    localparam CLK_PERIOD = 10;

    reg clk = 0, rstn = 0;
    reg        i_valid = 0;
    reg [5:0]  i_data  = 0;
    reg        i_last  = 0;
    wire       o_ready;
    wire [10:0] o_data;
    wire       o_last, o_valid;

    integer n_in = 0, n_out = 0;

    always #(CLK_PERIOD/2) clk = ~clk;

    // Pango APM sim model resolves GRS_INST.GRSNET up the hierarchy -- required
    GTP_GRS GRS_INST( .GRS_N(1'b1) );

    FIR u_fir (
        .i_clk                 (clk),
        .i_rstn                (rstn),
        .i_axi4s_data_tdata    (i_data),
        .i_axi4s_data_tlast    (i_last),
        .o_axi4s_data_tready   (o_ready),
        .i_axi4s_data_tvalid   (i_valid),
        .o_axi4s_data_tdata    (o_data),
        .o_axi4s_data_tlast    (o_last),
        .i_axi4s_data_tready   (1'b1),
        .o_axi4s_data_tvalid   (o_valid)
    );

    // beat counters + trace
    always @(posedge clk) begin
        if (i_valid) begin
            n_in = n_in + 1;
            $display("IN  %0t v=%b d=%0d(0x%02h) l=%b", $time, i_valid, i_data, i_data, i_last);
        end
        if (o_valid) begin
            n_out = n_out + 1;
            $display("OUT %0t v=%b d=%0d u=%0d l=%b  (bin=%b)", $time, o_valid, $signed(o_data), o_data, o_last, o_data);
        end
    end

    // one beat with data d; gap cycles have valid low
    task beat(input [5:0] d, input lst, input integer gap);
        begin
            @(negedge clk);
            i_valid <= 1'b1; i_data <= d; i_last <= lst;
            @(negedge clk);
            i_valid <= 1'b0; i_last <= 1'b0;
            repeat (gap) @(negedge clk);
        end
    endtask

    integer k;
    initial begin
        $display("=== FIR probe start ===");
        rstn = 0;
        repeat (5) @(negedge clk);
        rstn = 1;
        repeat (5) @(negedge clk);

        $display("=== TEST1: constant 32 x8 (expect u_sum=128 / s_sum=-128) ===");
        for (k = 0; k < 8; k = k + 1) beat(6'd32, 1'b0, 0);

        $display("=== TEST2: ramp 0..15 back-to-back ===");
        for (k = 0; k < 16; k = k + 1) beat(k[5:0], 1'b0, 0);

        $display("=== TEST3: step 0 then 63 with GAP=10 between beats ===");
        beat(6'd0,  1'b0, 10);
        beat(6'd63, 1'b0, 10);
        beat(6'd63, 1'b0, 10);
        beat(6'd0,  1'b0, 0);

        $display("=== TEST4: tlast with a single beat ===");
        beat(6'd10, 1'b1, 3);
        beat(6'd10, 1'b0, 0);

        $display("=== TEST5: long gap (hblank-like, 150 cycles) mid-stream ===");
        for (k = 0; k < 4; k = k + 1) beat(6'd40, 1'b0, 0);
        beat(6'd40, 1'b0, 150);
        for (k = 0; k < 4; k = k + 1) beat(6'd41, 1'b0, 0);

        repeat (30) @(negedge clk);
        $display("=== DONE n_in=%0d n_out=%0d ===", n_in, n_out);
        $finish;
    end
endmodule
