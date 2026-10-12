`timescale 1ns/1ps
//============================================================================
// tb_conv_top.v : conv_top module-level TB (需求(2), 3x3 + 量化全链)
//   golden: golden/ct_{in,bias,grp,exp}.mem (npu_golden.py, bit-exact incl.
//   zero_1 padding / 26bit acc wrap / 25bit pack / round / relu)
//   CIN=16 (1 tile) COUT=8 (1 group), H=6 W=8, bias 区 128B + 权重组 1152B.
//   exp 'xxxxxxxxxx' = don't care (帧头 2 拍窗口含上电未知值).
//   Dump  : golden/hw_out_conv_top.mem
//============================================================================
module tb_conv_top;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam H = 6, W = 8, COUT = 8;
    localparam NIN = H*W;               // 48
    localparam NBIAS = COUT;            // 8 words (128B)
    localparam NGRP = 9*COUT;           // 72 words (1152B)
    localparam NOUT = H*W;              // decoded contract: W windows per row (48)

    reg [127:0] inm   [0:NIN-1];
    reg [127:0] biasm [0:NBIAS-1];
    reg [127:0] grpm  [0:NGRP-1];
    reg [63:0]  expm  [0:NOUT-1];

    reg         type_c, start, stride, en_relu;
    reg  [31:0] col_num, row_num, calculate_num, calculate_cin_num, calculate_cout_num;
    reg  [15:0] scale_3;
    reg  [7:0]  zero_1, zero_3;
    reg  [31:0] s_addr, in_col_channel_num;
    wire [127:0] s_data;
    wire         s_valid, s_last;
    wire         s_ready;
    reg  [31:0]  weight_addr, weight_len, weight_sum;
    wire [127:0] weight;
    wire         weight_valid, weight_last;
    wire         weight_ready;
    wire [31:0]  s_cmd_addr, s_cmd_len;
    wire         s_cmd_valid;
    wire         s_cmd_ready;
    wire [31:0]  weight_cmd_addr, weight_cmd_len;
    wire         weight_cmd_valid;
    wire         weight_cmd_ready;
    wire [63:0]  m_data;
    wire         m_valid, m_last;
    reg          m_req;

    conv_top dut (
        .clk(clk), .rst(rst),
        .type(type_c), .start(start), .stride(stride), .en_relu(en_relu),
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
        .m_data(m_data), .m_valid(m_valid), .m_last(m_last),
        .m_req(m_req)
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
    // 布局: [0,128) bias 区, [128,1280) 权重组 (相对 weight_addr=0)
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
    reg [63:0] outm [0:NOUT-1];

    always @(posedge clk) begin
        if (!rst && m_valid) begin
            outm[ocnt] <= m_data;
            ocnt = ocnt + 1;
        end
    end

    initial begin
        $readmemh("golden/ct_in.mem",   inm);
        $readmemh("golden/ct_bias.mem", biasm);
        $readmemh("golden/ct_grp.mem",  grpm);
        $readmemh("golden/ct_exp.mem",  expm);
        type_c = 0; start = 0; stride = 0; en_relu = 1;
        col_num = W; row_num = H;
        calculate_num = 1; calculate_cin_num = 1; calculate_cout_num = 1;
        scale_3 = 16'h4000; zero_1 = 8'd3; zero_3 = 8'd5;
        s_addr = 0; in_col_channel_num = W*16;
        weight_addr = 0; weight_len = 128; weight_sum = 128 + NGRP*16;
        m_req = 1;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        start = 1; @(posedge clk); start = 0;
        wait (ocnt >= NOUT);
        repeat (10) @(posedge clk);
        // fallthrough: timeout branch below also dumps

        for (i = 0; i < NOUT; i = i + 1) begin
            if (expm[i] !== 64'hxxxxxxxxxxxxxxxx && outm[i] !== expm[i]) begin
                if (err < 8)
                    $display("[CT][ERR] idx=%0d got=%016h exp=%016h", i, outm[i], expm[i]);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_conv_top.mem", outm);
        if (ocnt == NOUT && err == 0)
            $display("[CT] TB_PASS  beats=%0d", ocnt);
        else
            $display("[CT] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NOUT, err);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("[CT][WARN] timeout ocnt=%0d (dump saved)", ocnt);
        $writememh("golden/hw_out_conv_top.mem", outm);
        $finish;
    end

endmodule
