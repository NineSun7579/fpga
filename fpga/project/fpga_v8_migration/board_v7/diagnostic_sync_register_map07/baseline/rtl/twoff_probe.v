// Method probe: both stages are functional primary outputs.
module map03_twoff_probe(input wire clk, rst, d, output wire q0, q1);
    (* syn_noprune=1 *) GTP_DFF_CE #(.GRS_EN("TRUE"),.INIT(1'b0)) ff0
        (.Q(q0),.D(d),.CLK(clk),.C(rst),.CE(1'b1));
    (* syn_noprune=1 *) GTP_DFF_CE #(.GRS_EN("TRUE"),.INIT(1'b0)) ff1
        (.Q(q1),.D(q0),.CLK(clk),.C(rst),.CE(1'b1));
endmodule
