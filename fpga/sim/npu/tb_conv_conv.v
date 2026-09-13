`timescale 1ns/1ps
//============================================================================
// tb_conv_conv.v : 3x3 conv core unit TB (需求(2))
//   golden: golden/c33_{w,d0,d1,d2,exp}.mem (npu_golden.py, raw 24-bit acc)
//   2 weight groups (ping-pong): 9 taps x 8 kernels broadcast, then a
//   3-row stream of W+2 beats (pad words at both ends, as in_ctrl would).
//   exp entries 'xxxxxx' = don't care (window not yet filled at frame head).
//   Dump  : golden/hw_out_conv_conv.mem
//============================================================================
module tb_conv_conv;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam NK = 8, NTAP = 9;
    localparam W = 8;               // real columns
    localparam BEATS = W + 2;       // + 2 pad words
    localparam NG = 2;
    localparam NW = NG*NTAP*NK;     // 144
    localparam NOUT = NG*W;         // decoded contract: W windows per group

    reg [127:0] wm [0:NW-1];
    reg [127:0] d0m [0:BEATS-1];
    reg [127:0] d1m [0:BEATS-1];
    reg [127:0] d2m [0:BEATS-1];
    reg [23:0]  expm[0:NOUT*NK-1];

    reg [127:0] w0,w1,w2,w3,w4,w5,w6,w7,w8;
    reg         weight_valid, weight_last, start, type_c;
    reg [127:0] s0, s1, s2;
    reg         s_valid, s_last;
    wire [8*24-1:0] m_data;
    wire            m_valid, m_last;

    conv_conv #(.CHA_PAR_IN(16), .CHA_PAR_OUT(8), .INT(8), .MUL_DELAY(4)) dut (
        .clk(clk), .rst(rst), .start(start), .type(type_c),
        .weight_0(w0), .weight_1(w1), .weight_2(w2),
        .weight_3(w3), .weight_4(w4), .weight_5(w5),
        .weight_6(w6), .weight_7(w7), .weight_8(w8),
        .weight_valid(weight_valid), .weight_last(weight_last),
        .s_data_0(s0), .s_data_1(s1), .s_data_2(s2),
        .s_valid(s_valid), .s_last(s_last),
        .m_data(m_data), .m_valid(m_valid), .m_last(m_last)
    );

    integer k, j, ocnt = 0, err = 0;
    reg [23:0] outm [0:NOUT*NK-1];

    always @(posedge clk) begin
        if (!rst && m_valid) begin
            for (k = 0; k < NK; k = k + 1)
                outm[ocnt*NK + k] <= m_data[k*24 +: 24];
            ocnt = ocnt + 1;
        end
    end

    // broadcast contract: per beat, all 9 tap ports present the SAME kernel kk
    // (tap x word for kernel kk); 8 beats per (cin,cout) group.
    task drive_weights(input integer gbase);
        integer kk;
        begin
            for (kk = 0; kk < NK; kk = kk + 1) begin
                w0 = wm[gbase + 0*NK + kk];
                w1 = wm[gbase + 1*NK + kk];
                w2 = wm[gbase + 2*NK + kk];
                w3 = wm[gbase + 3*NK + kk];
                w4 = wm[gbase + 4*NK + kk];
                w5 = wm[gbase + 5*NK + kk];
                w6 = wm[gbase + 6*NK + kk];
                w7 = wm[gbase + 7*NK + kk];
                w8 = wm[gbase + 8*NK + kk];
                weight_valid = 1;
                weight_last = (kk == NK-1);
                @(posedge clk);
            end
            weight_valid = 0; weight_last = 0;
        end
    endtask

    task drive_data;
        integer c;
        begin
            for (c = 0; c < BEATS; c = c + 1) begin
                s0 = d0m[c]; s1 = d1m[c]; s2 = d2m[c];
                s_valid = 1;
                s_last = (c == BEATS-1);
                @(posedge clk);
            end
            s_valid = 0; s_last = 0;
        end
    endtask

    integer g;
    initial begin
        $readmemh("golden/c33_w.mem",  wm);
        $readmemh("golden/c33_d0.mem", d0m);
        $readmemh("golden/c33_d1.mem", d1m);
        $readmemh("golden/c33_d2.mem", d2m);
        $readmemh("golden/c33_exp.mem", expm);
        {w0,w1,w2,w3,w4,w5,w6,w7,w8} = 0;
        weight_valid = 0; weight_last = 0; start = 0; type_c = 0;
        s0 = 0; s1 = 0; s2 = 0; s_valid = 0; s_last = 0;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        // group0: weights first, then data (weights of group1 interleave with
        // group0 data, as conv_weight/conv_ctrl do in the real chain)
        start = 1; @(posedge clk); start = 0;
        repeat (4) @(posedge clk);
        drive_weights(0);
        repeat (10) @(posedge clk);
        for (g = 0; g < NG; g = g + 1) begin
            if (g + 1 < NG) fork
                drive_data;
                begin
                    repeat (14) @(posedge clk);      // let group data start flowing
                    drive_weights((g + 1) * NTAP * NK);
                end
            join
            else
                drive_data;
            repeat (140) @(posedge clk);   // drain
        end
        // judge
        if (ocnt != NOUT)
            $display("[C33][WARN] out beats=%0d exp=%0d", ocnt, NOUT);
        for (j = 0; j < ocnt*NK && j < NOUT*NK; j = j + 1) begin
            if (expm[j] !== 24'hxxxxxx && outm[j] !== expm[j]) begin
                if (err < 8)
                    $display("[C33][ERR] idx=%0d got=%06h exp=%06h", j, outm[j], expm[j]);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_conv_conv.mem", outm);
        if (ocnt == NOUT && err == 0)
            $display("[C33] TB_PASS  beats=%0d", ocnt);
        else
            $display("[C33] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NOUT, err);
        $finish;
    end

    initial begin
        #800_000;
        $display("[C33] TB_FAIL  timeout ocnt=%0d", ocnt);
        $finish;
    end

endmodule
