`timescale 1ns/1ps
//============================================================================
// tb_sppf_unit.v : sppf_maxpool unit TB (需求(2))
//   golden: golden/sppu_row{0..4}.mem + sppu_exp.mem (5x5 stride-5 max)
//   5 row streams of W=10 words each (W/5=2 output beats).
//   Dump  : golden/hw_out_sppf_maxpool.mem
//============================================================================
module tb_sppf_unit;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam W = 10;
    localparam NOUT = W;          // stride-1: one output per column (p=2 zero pad)
    localparam NBEATS = W + 4;    // 2 zero pads each side

    reg [127:0] r0m [0:W-1];
    reg [127:0] r1m [0:W-1];
    reg [127:0] r2m [0:W-1];
    reg [127:0] r3m [0:W-1];
    reg [127:0] r4m [0:W-1];
    reg [7:0]   expm [0:NOUT*16-1];

    reg [127:0] s0, s1, s2, s3, s4;
    reg         s_valid, s_last;
    wire [127:0] m_data;
    wire         m_valid, m_last;

    sppf_maxpool #(.CHA_PAR_IN(16), .INT(8)) dut (
        .clk(clk), .rst(rst),
        .s_data_0(s0), .s_data_1(s1), .s_data_2(s2), .s_data_3(s3), .s_data_4(s4),
        .s_valid(s_valid), .s_last(s_last),
        .m_data(m_data), .m_valid(m_valid), .m_last(m_last)
    );

    integer i, ocnt = 0, err = 0;
    reg [7:0] outm [0:NOUT*16-1];

    always @(posedge clk) begin
        if (!rst && m_valid && (ocnt < NOUT)) begin
            for (i = 0; i < 16; i = i + 1)
                outm[ocnt*16 + i] <= m_data[i*8 +: 8];
            ocnt = ocnt + 1;
        end
    end

    integer c;
    initial begin
        $readmemh("golden/sppu_row0.mem", r0m);
        $readmemh("golden/sppu_row1.mem", r1m);
        $readmemh("golden/sppu_row2.mem", r2m);
        $readmemh("golden/sppu_row3.mem", r3m);
        $readmemh("golden/sppu_row4.mem", r4m);
        $readmemh("golden/sppu_exp.mem",  expm);
        {s0,s1,s2,s3,s4} = 0; s_valid = 0; s_last = 0;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        for (c = 0; c < NBEATS; c = c + 1) begin
            if (c == 0 || c == 1 || c == NBEATS-2 || c == NBEATS-1)
                {s0,s1,s2,s3,s4} = 128'd0;                       // zero pad word
            else begin
                {s0,s1,s2,s3,s4} = {r0m[c-2], r1m[c-2], r2m[c-2], r3m[c-2], r4m[c-2]};
            end
            s_valid = 1;
            s_last = (c == NBEATS-1);
            @(posedge clk);
        end
        s_valid = 0; s_last = 0;
        repeat (40) @(posedge clk);
        if (ocnt != NOUT)
            $display("[SPPU][WARN] out=%0d exp=%0d", ocnt, NOUT);
        for (i = 0; i < ocnt*16 && i < NOUT*16; i = i + 1) begin
            if (outm[i] !== expm[i]) begin
                if (err < 8)
                    $display("[SPPU][ERR] idx=%0d got=%02h exp=%02h", i, outm[i], expm[i]);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_sppf_maxpool.mem", outm);
        if (ocnt == NOUT && err == 0)
            $display("[SPPU] TB_PASS  beats=%0d", ocnt);
        else
            $display("[SPPU] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NOUT, err);
        $finish;
    end

    initial begin
        #200_000;
        $display("[SPPU] TB_FAIL  timeout ocnt=%0d", ocnt);
        $finish;
    end

endmodule
