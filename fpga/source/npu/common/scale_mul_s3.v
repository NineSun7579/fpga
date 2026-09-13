// (* syn_multstyle = "dsp" *)
module scale_mul_s3 #(
    parameter DATA_WIDTH  = 32,
              SCALE_WIDTH = 16,
              DELAY       = 1
)
(
    input  wire clk,
    input  wire signed [DATA_WIDTH-1 : 0]  A,
    input  wire signed [SCALE_WIDTH-1 : 0] B,
    output wire signed [DATA_WIDTH+SCALE_WIDTH-1 : 0] P
);

    generate
        if (DELAY == 0) begin : gen_delay_0
            assign P = $signed(A) * $signed(B);
        end
        else if (DELAY == 1) begin : gen_delay_1
            reg signed [DATA_WIDTH+SCALE_WIDTH-1 : 0] p_r;
            always @(posedge clk) begin
                p_r <= $signed(A) * $signed(B);
            end
            assign P = p_r;
        end
        else if (DELAY == 2) begin : gen_delay_2
            reg signed [DATA_WIDTH-1 : 0]             a_r;
            reg signed [SCALE_WIDTH-1 : 0]            b_r;
            reg signed [DATA_WIDTH+SCALE_WIDTH-1 : 0] p_r;
            
            always @(posedge clk) begin
                a_r <= A;
                b_r <= B;
                p_r <= $signed(a_r) * $signed(b_r);
            end
            assign P = p_r;
        end
        else begin : gen_delay_N
            reg signed [DATA_WIDTH-1 : 0]             a_r;
            reg signed [SCALE_WIDTH-1 : 0]            b_r;
            reg signed [DATA_WIDTH+SCALE_WIDTH-1 : 0] mult_r;
            
            localparam REMAIN_DELAY = DELAY - 2; 
            reg signed [DATA_WIDTH+SCALE_WIDTH-1 : 0] pipe [0 : REMAIN_DELAY-1];
            
            integer i;
            always @(posedge clk) begin
                a_r    <= A;
                b_r    <= B;
                mult_r <= $signed(a_r) * $signed(b_r);
                pipe[0] <= mult_r;
                for (i = 1; i < REMAIN_DELAY; i = i + 1) begin
                    pipe[i] <= pipe[i-1];
                end
            end
            
            assign P = pipe[REMAIN_DELAY-1];
        end
    endgenerate

endmodule
