`timescale 1ns/1ps
//============================================================================
// tb_c33_decode.v : conv_conv window-mapping decoder (debug experiment)
//   data (r,c,i=0) = 10*c + r + 1   (i>0 = 0)  -> distinct per (row,col)
//   weight kernel0: tap t byte0 = 100*(t+1), others 0
//   -> out[k0] = SUM over window (r,c): 100*(tapidx+1) * (10c+r+1)
//   Each tap contributes a distinct code; decode which (row,col) each tap
//   actually multiplies from one output value. All other kernels = 0.
//============================================================================
module tb_c33_decode;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam NK = 8, NTAP = 9;
    localparam BEATS = 12;          // 2 pad + 8 real + 2 pad

    reg [127:0] wtap [0:NTAP-1];    // tap t word: byte0 = 100*(t+1)
    reg [127:0] drow [0:2][0:BEATS-1];
    reg [23:0]  dummy;

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

    integer k, kk, c, oc = 0, t_int;
    reg [127:0] dw;

    task drive_weights;
        begin
            for (kk = 0; kk < NK; kk = kk + 1) begin
                w0 = (kk == 0) ? wtap[0] : 128'd0;
                w1 = (kk == 0) ? wtap[1] : 128'd0;
                w2 = (kk == 0) ? wtap[2] : 128'd0;
                w3 = (kk == 0) ? wtap[3] : 128'd0;
                w4 = (kk == 0) ? wtap[4] : 128'd0;
                w5 = (kk == 0) ? wtap[5] : 128'd0;
                w6 = (kk == 0) ? wtap[6] : 128'd0;
                w7 = (kk == 0) ? wtap[7] : 128'd0;
                w8 = (kk == 0) ? wtap[8] : 128'd0;
                weight_valid = 1;
                weight_last  = (kk == NK-1);
                @(posedge clk);
            end
            weight_valid = 0; weight_last = 0;
        end
    endtask

    initial begin
        // build stimulus
        for (t_int = 0; t_int < NTAP; t_int = t_int + 1) begin
            wtap[t_int] = 128'd0;
            wtap[t_int][7:0] = 8'd100 * (t_int + 1);
        end
        for (c = 0; c < BEATS; c = c + 1) begin
            drow[0][c] = 128'd0; drow[1][c] = 128'd0; drow[2][c] = 128'd0;
            drow[0][c][7:0] = (c <= 1 || c >= BEATS-2) ? 8'd200 : 8'd10*(c-2) + 0 + 1; // row0
            drow[1][c][7:0] = (c <= 1 || c >= BEATS-2) ? 8'd201 : 8'd10*(c-2) + 1 + 1; // row1
            drow[2][c][7:0] = (c <= 1 || c >= BEATS-2) ? 8'd202 : 8'd10*(c-2) + 2 + 1; // row2
        end
        {w0,w1,w2,w3,w4,w5,w6,w7,w8} = 0;
        weight_valid = 0; weight_last = 0; start = 0; type_c = 0;
        s0 = 0; s1 = 0; s2 = 0; s_valid = 0; s_last = 0;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        start = 1; @(posedge clk); start = 0;
        repeat (4) @(posedge clk);
        drive_weights;
        repeat (10) @(posedge clk);
        for (c = 0; c < BEATS; c = c + 1) begin
            s0 = drow[0][c]; s1 = drow[1][c]; s2 = drow[2][c];
            s_valid = 1;
            s_last = (c == BEATS-1);
            @(posedge clk);
        end
        s_valid = 0; s_last = 0;
        repeat (200) @(posedge clk);
        $display("[DEC] done outputs=%0d", oc);
        $finish;
    end

    always @(posedge clk) begin
        if (!rst && m_valid) begin
            $display("[DEC] t=%0t out#%0d k0=%0d k1=%0d k2=%0d k3=%0d k4=%0d k5=%0d k6=%0d k7=%0d",
                     $time, oc,
                     $signed(m_data[0*24 +: 24]), $signed(m_data[1*24 +: 24]),
                     $signed(m_data[2*24 +: 24]), $signed(m_data[3*24 +: 24]),
                     $signed(m_data[4*24 +: 24]), $signed(m_data[5*24 +: 24]),
                     $signed(m_data[6*24 +: 24]), $signed(m_data[7*24 +: 24]));
            oc = oc + 1;
        end
    end

    initial begin
        #500_000;
        $finish;
    end

endmodule
