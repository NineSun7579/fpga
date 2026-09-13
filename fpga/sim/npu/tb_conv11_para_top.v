`timescale 1ns/1ps
//============================================================================
// tb_conv11_para_top.v : 1x1 conv module-level TB (需求(2), 完整量化 + out_buf)
//   golden: golden/p11_{in,bias,w,exp}.mem (npu_golden.py, banker's rounding)
//   CIN=16 (1 tile) COUT=8 (1 group), H=6 W=8. m_cmd/m_ready tie ready.
//   Dump  : golden/hw_out_conv11_para_top.mem
//============================================================================
module tb_conv11_para_top;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam H = 6, W = 8, COUT = 8;
    localparam NIN = H*W;               // 48
    localparam NBIAS = COUT;            // 8 words
    localparam NGRP = COUT;             // 1 tap x 8 kernels = 8 words
    localparam NOUT = H*W;              // 48

    reg [127:0] inm   [0:NIN-1];
    reg [127:0] biasm [0:NBIAS-1];
    reg [127:0] grpm  [0:NGRP-1];
    reg [63:0]  expm  [0:NOUT-1];

    reg          type_c, start, en_relu;
    reg   [31:0] col_num, row_num, calculate_num, calculate_cin_num, calculate_cout_num;
    reg   [15:0] scale_3;
    reg   [7:0]  zero_1, zero_3;
    reg   [31:0] s_addr, in_col_channel_num;
    wire  [127:0] s_data;
    wire          s_valid, s_last;
    wire         s_ready;
    reg   [31:0] weight_addr, weight_len, weight_sum;
    wire  [127:0] weight;
    wire          weight_valid, weight_last;
    wire         weight_ready;
    wire  [31:0] s_cmd_addr, s_cmd_len;
    wire         s_cmd_valid;
    wire         s_cmd_ready;
    wire  [31:0] weight_cmd_addr, weight_cmd_len;
    wire         weight_cmd_valid;
    wire         weight_cmd_ready;
    reg   [31:0] m_addr, out_col_channel_num;
    wire  [127:0] m_data;
    wire          m_last, m_valid;
    reg           m_ready;
    wire          m_cmd_addr, m_cmd_len, m_cmd_valid;
    reg           m_cmd_ready;
    wire          calculate_end;
    reg           calculate_end_receive;

    conv11_para_top dut (
        .clk(clk), .rst(rst),
        .type(type_c), .start(start), .stride(1'b0), .en_relu(en_relu),
        .col_num(col_num), .row_num(row_num),
        .calculate_num(calculate_num),
        .calculate_cin_num(calculate_cin_num),
        .calculate_cout_num(calculate_cout_num),
        .scale_3(scale_3), .zero_1(zero_1), .zero_3(zero_3),
        .s_addr(s_addr),
        .in_col_channel_num(in_col_channel_num),
        .s_data(s_data), .s_valid(s_valid), .s_last(s_last), .s_ready(s_ready),
        .weight_addr(weight_addr), .weight_len(weight_len), .weight_sum(weight_sum),
        .weight(weight), .weight_valid(weight_valid), .weight_last(weight_last),
        .weight_ready(weight_ready),
        .s_cmd_addr(s_cmd_addr), .s_cmd_len(s_cmd_len),
        .s_cmd_valid(s_cmd_valid), .s_cmd_ready(s_cmd_ready),
        .weight_cmd_addr(weight_cmd_addr), .weight_cmd_len(weight_cmd_len),
        .weight_cmd_valid(weight_cmd_valid), .weight_cmd_ready(weight_cmd_ready),
        .m_addr(m_addr),
        .out_col_channel_num(out_col_channel_num),
        .m_data(m_data), .m_last(m_last), .m_valid(m_valid), .m_ready(m_ready),
        .m_cmd_addr(m_cmd_addr), .m_cmd_len(m_cmd_len),
        .m_cmd_valid(m_cmd_valid), .m_cmd_ready(m_cmd_ready),
        .calculate_end(calculate_end),
        .calculate_end_receive(calculate_end_receive)
    );

    //---------------- fake input DMA ----------------
    reg         i_vld = 0;
    reg [127:0] i_dat = 0;
    reg [31:0]  i_widx = 0, i_left = 0;
    assign s_data  = i_dat;
    assign s_valid = i_vld;
    wire i_last_w = (i_left == 16);
    assign s_last  = i_vld && i_last_w;
    assign s_cmd_ready = !i_vld;
    always @(posedge clk) begin
        if (rst) begin i_vld <= 0; i_widx <= 0; i_left <= 0; end
        else if (!i_vld) begin
            if (s_cmd_valid && s_cmd_ready) begin
                i_widx <= s_cmd_addr >> 4;
                i_left <= s_cmd_len;
                i_dat  <= inm[s_cmd_addr >> 4];
                i_vld  <= 1;
            end
        end
        else if (s_ready) begin
            if (i_last_w) i_vld <= 0;
            else begin
                i_widx <= i_widx + 1;
                i_left <= i_left - 16;
                i_dat  <= inm[i_widx + 1];
            end
        end
    end

    //---------------- fake weight DMA ----------------
    reg         w_vld = 0;
    reg [127:0] w_dat = 0;
    reg [31:0]  w_addr = 0, w_left = 0;
    assign weight  = w_dat;
    assign weight_valid = w_vld;
    wire w_last_w = (w_left == 16);
    assign weight_last  = w_vld && w_last_w;
    assign weight_cmd_ready = !w_vld;
    function [127:0] wt_word(input [31:0] a);
        wt_word = (a < 128) ? biasm[a >> 4] : grpm[(a - 128) >> 4];
    endfunction
    always @(posedge clk) begin
        if (rst) begin w_vld <= 0; w_addr <= 0; w_left <= 0; end
        else if (!w_vld) begin
            if (weight_cmd_valid && weight_cmd_ready) begin
                w_addr <= weight_cmd_addr;
                w_left <= weight_cmd_len;
                w_dat  <= wt_word(weight_cmd_addr);
                w_vld  <= 1;
            end
        end
        else if (weight_ready) begin
            if (w_last_w) w_vld <= 0;
            else begin
                w_addr <= w_addr + 16;
                w_left <= w_left - 16;
                w_dat  <= wt_word(w_addr + 16);
            end
        end
    end

    //---------------- collect + judge ----------------
    integer ocnt = 0, err = 0, i;
    reg [127:0] outm [0:NOUT/2-1];   // m_data is 128-bit: packs 2 columns (8 kernels each)

    always @(posedge clk) begin
        if (!rst && m_valid && m_ready && (ocnt < NOUT/2)) begin
            outm[ocnt] <= m_data;
            ocnt = ocnt + 1;
        end
    end

    initial begin
        $readmemh("golden/p11_in.mem",   inm);
        $readmemh("golden/p11_bias.mem", biasm);
        $readmemh("golden/p11_w.mem",    grpm);
        $readmemh("golden/p11_exp.mem",  expm);
        type_c = 1; start = 0; en_relu = 1;
        col_num = W; row_num = H;
        calculate_num = 1; calculate_cin_num = 1; calculate_cout_num = 1;
        scale_3 = 16'h6000; zero_1 = 8'd1; zero_3 = 8'd2;
        s_addr = 0; in_col_channel_num = W*16;
        weight_addr = 0; weight_len = 128; weight_sum = 256;
        m_addr = 0; out_col_channel_num = W*COUT;   // out row bytes = cols x 8 kernels (out_buf word = 16B packs 2 cols)
        m_ready = 1; m_cmd_ready = 1; calculate_end_receive = 1;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        start = 1; @(posedge clk); start = 0;
        wait (ocnt >= NOUT/2);
        repeat (10) @(posedge clk);
        // 128-bit word = [low64: column 2k] [high64: column 2k+1] (verified by compare)
        for (i = 0; i < NOUT/2; i = i + 1) begin
            if (outm[i][63:0]   !== expm[2*i]) begin
                if (err < 8) $display("[P11][ERR] w%0d LOW  got=%016h exp=%016h", i, outm[i][63:0], expm[2*i]);
                err = err + 1;
            end
            if (outm[i][127:64] !== expm[2*i+1]) begin
                if (err < 8) $display("[P11][ERR] w%0d HIGH got=%016h exp=%016h", i, outm[i][127:64], expm[2*i+1]);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_conv11_para_top.mem", outm);
        if (ocnt == NOUT/2 && err == 0)
            $display("[P11] TB_PASS  words=%0d (cols=%0d)", ocnt, ocnt*2);
        else
            $display("[P11] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NOUT/2, err);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("[P11][WARN] timeout ocnt=%0d (dump saved)", ocnt);
        $writememh("golden/hw_out_conv11_para_top.mem", outm);
        $finish;
    end

endmodule
