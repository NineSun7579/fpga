module sfp_decode_select #(parameter SFP_NEW_PARSER=0)(
 input sfp_rx_clk,sfp_rx_rst_n,sfp_rx_en,sfp_raw_en,
 input [31:0] sfp_rxd,sfp_raw_d,input [3:0] sfp_rxk,sfp_raw_k,
 output sfp_vs,sfp_hs,sfp_de,output [15:0] sfp_pix,
 output sfp_parser_overflow,sfp_malformed);
generate if (SFP_NEW_PARSER) begin : sfp_new_rx
rx_symbol_candidate u_parser(.i_clk(sfp_rx_clk),.i_rst_n(sfp_rx_rst_n),
 .i_en(sfp_raw_en),.i_rxd(sfp_raw_d),.i_rxk(sfp_raw_k),
 .o_vs(sfp_vs),.o_hs(sfp_hs),.o_de(sfp_de),.o_pix(sfp_pix),
 .o_overflow(sfp_parser_overflow),.o_malformed(sfp_malformed));
end else begin : sfp_old_rx
assign sfp_malformed=1'b0;
sfp_video_rx u_sfp_video_rx (
    .i_clk      (sfp_rx_clk),
    .i_rst_n    (sfp_rx_rst_n),
    .i_en       (sfp_rx_en),
    .i_rxd      (sfp_rxd),
    .i_rxk      (sfp_rxk),
    .o_vs       (sfp_vs),
    .o_hs       (sfp_hs),
    .o_de       (sfp_de),
    .o_pix      (sfp_pix),
    .o_overflow (sfp_parser_overflow)
);
end endgenerate
endmodule
