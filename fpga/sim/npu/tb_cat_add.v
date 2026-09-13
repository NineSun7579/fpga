`timescale 1ns/1ps
//============================================================================
// tb_cat_add.v : cat_add unit TB (需求(2))
//   golden: golden/cat_{d0,d1,mode,exp,regs}.mem  (npu_golden.py, bit-exact)
//   3 regions (realistic scale / exact-0.5 rounding / saturation), each with
//   add mode + cat mode (single-stream) beats; scales change per region with
//   20 idle cycles drain (pipeline ALL_DELAY=11).
//   Dump  : golden/hw_out_cat_add.mem (one byte per beat = m_data[7:0])
//============================================================================
module tb_cat_add;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam NREG   = 3;
    localparam NBEATS = 93;

    reg [127:0] d0m [0:NBEATS-1];
    reg [127:0] d1m [0:NBEATS-1];
    reg [7:0]   mdm [0:NBEATS-1];
    reg [7:0]   expm[0:NBEATS-1];
    reg [31:0]  regm[0:4*NREG-1];   // s1, s2, s3, {z2,z1} per region

    reg [127:0] s_data_0, s_data_1;
    reg         s_valid_0, s_valid_1, s_last;
    reg  [15:0] scale_1, scale_2;
    reg  [31:0] scale_3;   // cat_add scale_3 port is 32-bit (Q30)
    reg  [31:0] scale3_full;
    reg  [7:0]  zero_1, zero_2;
    wire [127:0] m_data;
    wire         m_valid, m_last;

    cat_add dut (
        .clk(clk), .rst(rst), .start(1'b0),
        .scale_1(scale_1), .scale_2(scale_2),
        .scale_3(scale_3),
        .zero_1(zero_1), .zero_2(zero_2),
        .s_data_0(s_data_0), .s_data_1(s_data_1),
        .s_valid_0(s_valid_0), .s_valid_1(s_valid_1), .s_last(s_last),
        .m_data(m_data), .m_valid(m_valid), .m_last(m_last)
    );

    integer beat = 0, ocnt = 0, err = 0;
    reg [127:0] outm [0:NBEATS-1];
    reg [127:0] expfull;
    integer gi;
    reg [7:0] cur_reg, cur_sub;
    reg [7:0] exp_byte;

    // collect
    always @(posedge clk) begin
        if (!rst && m_valid) begin
            outm[ocnt] <= m_data;
            ocnt = ocnt + 1;
        end
    end

    // driver
    integer gap;
    initial begin
        $readmemh("golden/cat_d0.mem",   d0m);
        $readmemh("golden/cat_d1.mem",   d1m);
        $readmemh("golden/cat_mode.mem", mdm);
        $readmemh("golden/cat_exp.mem",  expm);
        $readmemh("golden/cat_regs.mem", regm);
        s_data_0 = 0; s_data_1 = 0; s_valid_0 = 0; s_valid_1 = 0; s_last = 0;
        scale_1 = 0; scale_2 = 0; scale_3 = 0; zero_1 = 0; zero_2 = 0;
        cur_reg = 8'hFF;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        for (beat = 0; beat < NBEATS; beat = beat + 1) begin
            cur_sub = mdm[beat][1:0];
            if (mdm[beat][7:2] !== cur_reg) begin
                cur_reg = mdm[beat][7:2];
                gi = cur_reg * 4;
                scale_1 = regm[gi];
                scale_2 = regm[gi+1];
                scale3_full = regm[gi+2];
                scale_3 = scale3_full;
                {zero_2, zero_1} = regm[gi+3][15:0];
                repeat (20) @(posedge clk);   // drain pipeline before new scales
            end
            s_data_0 = d0m[beat];
            s_data_1 = d1m[beat];
            s_valid_0 = (cur_sub == 2'd0) || (cur_sub == 2'd1);
            s_valid_1 = (cur_sub == 2'd0) || (cur_sub == 2'd2);
            s_last = (beat == NBEATS-1);
            @(posedge clk);
            gap = $random & 3;
            repeat (gap) begin
                s_valid_0 = 0; s_valid_1 = 0; s_last = 0;
                @(posedge clk);
            end
        end
        s_valid_0 = 0; s_valid_1 = 0;
        repeat (60) @(posedge clk);      // drain
        // judge
        for (beat = 0; beat < NBEATS && beat < ocnt; beat = beat + 1) begin
            exp_byte = expm[beat];
            expfull = {16{exp_byte}};
            if (outm[beat] !== expfull) begin
                if (err < 8)
                    $display("[CAT][ERR] beat=%0d got=%04h_%04h exp_byte=%02h",
                             beat, outm[beat][63:48], outm[beat][15:0], exp_byte);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_cat_add.mem", outm, 0, NBEATS-1);
        if (ocnt == NBEATS && err == 0)
            $display("[CAT] TB_PASS  beats=%0d", ocnt);
        else
            $display("[CAT] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NBEATS, err);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("[CAT] TB_FAIL  timeout ocnt=%0d", ocnt);
        $finish;
    end

endmodule
