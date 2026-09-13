`timescale 1ns/1ps
//============================================================================
// tb_conv11_conv.v : 1x1 conv core unit TB (需求(2))
//   golden: golden/c11_{w,d,exp}.mem  (npu_golden.py, raw 24-bit acc)
//   weight_4 single tap (8 kernels x 16ch), single data stream, N beats.
//   Dump  : golden/hw_out_conv11_conv.mem (8 x 24bit per beat)
//============================================================================
module tb_conv11_conv;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam NK = 8;
    localparam NBEATS = 40;

    reg [127:0] wm  [0:NK-1];
    reg [127:0] dm  [0:NBEATS-1];
    reg [23:0]  expm[0:NK*NBEATS-1];

    reg [127:0] weight_4;
    reg         weight_valid, weight_last, start;
    reg [127:0] s_data_1;
    reg         s_valid, s_last;
    wire [8*24-1:0] m_data;
    wire            m_valid, m_last;

    conv11_conv #(.CHA_PAR_IN(16), .CHA_PAR_OUT(8), .INT(8), .MUL_DELAY(4)) dut (
        .clk(clk), .rst(rst), .start(start),
        .weight_4(weight_4), .weight_valid(weight_valid), .weight_last(weight_last),
        .s_data_1(s_data_1), .s_valid(s_valid), .s_last(s_last),
        .m_data(m_data), .m_valid(m_valid), .m_last(m_last)
    );

    integer k, j, ocnt = 0, err = 0;
    reg [23:0] outm [0:NK*NBEATS-1];

    always @(posedge clk) begin
        if (!rst && m_valid) begin
            for (k = 0; k < NK; k = k + 1)
                outm[ocnt*NK + k] <= m_data[k*24 +: 24];
            ocnt = ocnt + 1;
        end
    end

    integer beat;
    initial begin
        $readmemh("golden/c11_w.mem",   wm);
        $readmemh("golden/c11_d.mem",   dm);
        $readmemh("golden/c11_exp.mem", expm);
        weight_4 = 0; weight_valid = 0; weight_last = 0;
        s_data_1 = 0; s_valid = 0; s_last = 0; start = 0;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        start = 1; @(posedge clk); start = 0;
        // weight broadcast: 8 beats (kernel-major)
        repeat (4) @(posedge clk);
        for (k = 0; k < NK; k = k + 1) begin
            weight_4 = wm[k];
            weight_valid = 1;
            weight_last = (k == NK-1);
            @(posedge clk);
        end
        weight_valid = 0; weight_last = 0;
        repeat (10) @(posedge clk);
        // data stream
        for (beat = 0; beat < NBEATS; beat = beat + 1) begin
            s_data_1 = dm[beat];
            s_valid = 1;
            s_last = (beat == NBEATS-1);
            @(posedge clk);
        end
        s_valid = 0; s_last = 0;
        repeat (80) @(posedge clk);
        // judge
        if (ocnt != NBEATS-2)
            $display("[C11][WARN] out beats=%0d exp=%0d", ocnt, NBEATS-2);
        for (j = 0; j < ocnt*NK && j < (NBEATS-2)*NK; j = j + 1) begin
            if (outm[j] !== expm[j + NK]) begin
                if (err < 8)
                    $display("[C11][ERR] idx=%0d got=%06h exp=%06h", j, outm[j], expm[j + NK]);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_conv11_conv.mem", outm);
        if (ocnt == NBEATS-2 && err == 0)
            $display("[C11] TB_PASS  beats=%0d", ocnt);
        else
            $display("[C11] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NBEATS, err);
        $finish;
    end

    initial begin
        #500_000;
        $display("[C11] TB_FAIL  timeout ocnt=%0d", ocnt);
        $finish;
    end

endmodule
