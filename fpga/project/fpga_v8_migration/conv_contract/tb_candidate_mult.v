`timescale 1ns/1ps
module fpga_v8_tb_candidate_mult;
    parameter integer MUL_DELAY = 4;
    reg clk = 0;
    always #5 clk = ~clk;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    reg [7:0] a = 0, b = 0, c = 0;
    wire [15:0] ac, bc;
    generate
        if (MUL_DELAY == 4) begin : gen_default_delay
            fpga_v8_conv_mul_pair dut(
                .clk(clk), .a(a), .b(b), .c(c), .a_c(ac), .b_c(bc));
        end else begin : gen_explicit_delay
            fpga_v8_conv_mul_pair #(.INT(8), .MUL_DELAY(MUL_DELAY)) dut(
                .clk(clk), .a(a), .b(b), .c(c), .a_c(ac), .b_c(bc));
        end
    endgenerate
    integer fd, i, cyc = 0, stim = -1;
    always @(posedge clk) begin
        cyc = cyc + 1;
        #1;
        $fdisplay(fd, "%0d %0d %02h %02h %02h %04h %04h", cyc, stim, a, b, c, ac, bc);
    end
    initial begin
        fd = $fopen("mul_observed.txt", "w");
        repeat (12) @(negedge clk);
        for (i = 0; i < 65536; i = i + 1) begin
            a = i / 256;
            b = ~a;
            c = i % 256;
            stim = i;
            @(negedge clk);
        end
        a = 0; b = 0; c = 0; stim = -1;
        repeat (12) @(negedge clk);
        $fclose(fd);
        $display("CANDIDATE_MULT_DONE");
        $finish;
    end
    initial begin #1000000; $display("CONTRACT_TIMEOUT"); $finish; end
endmodule

module fpga_v8_tb_candidate_mult_bad;
    parameter integer INT = 8, MUL_DELAY = 1;
    reg clk = 0;
    always #5 clk = ~clk;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    wire [INT*2-1:0] ac, bc;
    fpga_v8_conv_mul_pair #(.INT(INT), .MUL_DELAY(MUL_DELAY)) dut(
        .clk(clk), .a({INT{1'b0}}), .b({INT{1'b0}}), .c({INT{1'b0}}),
        .a_c(ac), .b_c(bc));
    initial begin
        #20;
        $display("INVALID_CONFIG_ACCEPTED");
        $finish;
    end
endmodule
