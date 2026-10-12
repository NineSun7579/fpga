`timescale 1ns/1ps

// Isolated candidate shared by the general and dedicated convolution cores.
// a/b are signed int8 weights; c is a full-range unsigned 8-bit activation.
// An input sampled at edge n appears after edge n + MUL_DELAY - 1.
// There is no reset/valid interface: disregard only the initial pipeline fill.
module fpga_v8_conv_mul_pair #(
    parameter integer INT = 8,
    parameter integer MUL_DELAY = 4
)(
    input  wire                 clk,
    input  wire [INT-1:0]       a,
    input  wire [INT-1:0]       b,
    input  wire [INT-1:0]       c,
    output wire [INT*2-1:0]     a_c,
    output wire [INT*2-1:0]     b_c
);
    // Official GTP_APM_E2: P = USE_POSTADD ? pi : mi. P_REG is bypassed
    // in this mode; X/Y_REG=1 plus MULT_REG=1 provide TWO active stages.
    localparam integer DELAY = MUL_DELAY - 2;

    generate
        if (INT != 8) begin : gen_invalid_int
            // Intentionally undefined: fail elaboration/synthesis, not just log.
            fpga_v8_config_error_INT_must_be_8 invalid_configuration();
        end else if (MUL_DELAY < 2) begin : gen_invalid_delay
            fpga_v8_config_error_MUL_DELAY_must_be_at_least_2 invalid_configuration();
        end else begin : gen_valid
            wire signed [11:0] a_ext = {{4{a[7]}}, a};
            wire signed [11:0] b_ext = {{4{b[7]}}, b};
            wire [8:0] c_ext = {1'b0, c};
            wire [29:0] x_in = {6'b0, a_ext, b_ext};
            wire [17:0] y_in = {c_ext, c_ext};
            wire [47:0] result;

            GTP_APM_E2 #(
                .GRS_EN("TRUE"), .ASYNC_RST(0),
                .X_REG(1), .XB_REG(0), .Y_REG(1), .Z_REG(0),
                .MULT_REG(1), .P_REG(1),
                .USE_SIMD(1), .USE_MULT(1), .USE_POSTADD(0),
                .USE_PREADD(0), .PREADD_REG(0),
                .X_SEL(0), .XB_SEL(0), .CXO_REG(0), .CPO_REG(0),
                .MODEY_REG(0), .MODEZ_REG(0), .MODEIN_REG(0),
                .ROUNDMODE_SEL(0), .USE_ACCLOW(0), .CIN_SEL(0),
                .P_INIT0(48'b0), .P_INIT1(48'b0)
            ) u_apm_two_active_stages (
                .P(result), .CPO(), .COUT(), .CXO(), .CXBO(),
                .X(x_in), .CXI(30'b0), .CXBI(25'b0), .XB(25'b0),
                .Y(y_in), .Z(48'b0), .CPI(48'b0), .CIN(1'b0),
                .MODEIN(5'b00110), .MODEY(3'b000), .MODEZ(4'b0000),
                .CLK(clk),
                .CEX1(1'b1), .CEX2(1'b1), .CEX3(1'b1), .CEXB(1'b1),
                .CEY1(1'b1), .CEY2(1'b1), .CEZ(1'b1), .CEPRE(1'b1),
                .CEM(1'b1), .CEP(1'b1),
                .CEMODEY(1'b1), .CEMODEZ(1'b1), .CEMODEIN(1'b1),
                .RSTX(1'b0), .RSTXB(1'b0), .RSTY(1'b0), .RSTZ(1'b0),
                .RSTPRE(1'b0), .RSTM(1'b0), .RSTP(1'b0),
                .RSTMODEY(1'b0), .RSTMODEZ(1'b0), .RSTMODEIN(1'b0)
            );

            // Each signed 12x9 SIMD product is 24 bits. Both int8*u8
            // products fit signed16; preserve the exact low 16 bits per lane.
            wire [15:0] result_a_c = result[39:24];
            wire [15:0] result_b_c = result[15:0];
            wire [31:0] result_packed = {result_a_c, result_b_c};

            if (DELAY > 0) begin : gen_pipeline
                reg [31:0] pipe [0:DELAY-1];
                integer i;
                always @(posedge clk) begin
                    pipe[0] <= result_packed;
                    for (i = 1; i < DELAY; i = i + 1)
                        pipe[i] <= pipe[i-1];
                end
                assign a_c = pipe[DELAY-1][31:16];
                assign b_c = pipe[DELAY-1][15:0];
            end else begin : gen_bypass
                // MUL_DELAY=2: no external stages and no zero-length array.
                assign a_c = result_a_c;
                assign b_c = result_b_c;
            end
        end
    endgenerate
endmodule
