`timescale 1ns/1ps
//============================================================================
// gtp_apm_e2_sim.v : GTP_APM_E2 behavioral sim model (conv/conv11 NPU TB only)
//   Matches the configuration used by conv_mul_E2 / conv11_mul_E2:
//   X_REG=1, Y_REG=1, MULT_REG=1, P_REG=1  ->  3-cycle latency
//   USE_SIMD=1: X[29:24]=pad X[23:12]=a(12b signed) X[11:0]=b(12b signed)
//               Y[17:9]=c(9b unsigned)  Y[8:0]=c(9b unsigned)
//               P[47:24]=a*c (24b)  P[23:0]=b*c (24b)
//============================================================================
module GTP_APM_E2 #(
    parameter GRS_EN      = "TRUE",
    parameter ASYNC_RST   = 0,
    parameter X_REG       = 0,
    parameter XB_REG      = 0,
    parameter Y_REG       = 0,
    parameter Z_REG       = 0,
    parameter MULT_REG    = 0,
    parameter P_REG       = 0,
    parameter USE_SIMD    = 1,
    parameter USE_MULT    = 1,
    parameter USE_POSTADD = 0,
    parameter X_SEL       = 0,
    parameter XB_SEL      = 0
)(
    output wire [47:0] P,
    input  wire        CLK,
    input  wire [29:0] X,
    input  wire [17:0] Y,
    input  wire        CEX1, CEX2, CEY1, CEY2, CEM, CEP,
    input  wire [4:0]  MODEIN,
    input  wire [2:0]  MODEY,
    input  wire [3:0]  MODEZ,
    input  wire [24:0] XB,
    input  wire [47:0] Z,
    input  wire [47:0] CPI,
    input  wire        CIN,
    input  wire        RSTX, RSTY, RSTM, RSTP
);

    reg  [29:0] x_r;
    reg  [17:0] y_r;
    reg  [47:0] mult_r;
    reg  [47:0] p_r;

    wire signed [11:0] a_w = x_r[23:12];
    wire signed [11:0] b_w = x_r[11:0];
    wire        [8:0]  ca_w = y_r[17:9];
    wire        [8:0]  cb_w = y_r[8:0];
    wire signed [23:0] pa_w = a_w * $signed({1'b0, ca_w});
    wire signed [23:0] pb_w = b_w * $signed({1'b0, cb_w});

    always @(posedge CLK) begin
        x_r   <= X;                      // X_REG=1
        y_r   <= Y;                      // Y_REG=1
        mult_r <= {pa_w, pb_w};          // MULT_REG=1
        p_r   <= mult_r;                 // P_REG=1
    end

    assign P = p_r;

endmodule
