`timescale 1ns/1ps
// Digital test clock/IP mocks only. All mode, keys, resets, camera startup,
// merge, FIFO and packetizer RTL in tb_diagnostic_boot is production code.
module pll(input clkin1, output clkout0,clkout1,clkout2,pll_lock);
    assign clkout0=clkin1; assign clkout1=clkin1; assign clkout2=clkin1;
    reg lock=0;
    initial begin #100;lock=1;end
    assign pll_lock=lock;
endmodule
module GTP_IOCLKDIV #(parameter DIV_FACTOR="2",parameter GRS_EN="TRUE")(
    input CLKIN, RST_N, output CLKDIVOUT);
    reg divide=0;
    always @(posedge CLKIN or negedge RST_N)
        if(!RST_N)divide<=0;else divide<=~divide;
    assign CLKDIVOUT=divide;
endmodule
module GTP_IOCLKBUF #(parameter GATE_EN="FALSE")(
    input CLKIN,DI,output CLKOUT);
    assign CLKOUT=CLKIN;
endmodule
module hsst_test(
    input i_free_clk,i_p_refckp_0,i_p_refckn_0,i_wtchdg_clr_0,
    output o_wtchdg_st_0,o_pll_done_0,o_txlane_done_2,o_txlane_done_3,
    output o_rxlane_done_2,o_rxlane_done_3,o_p_clk2core_tx_2,
    input i_p_tx2_clk_fr_core,i_p_tx3_clk_fr_core,i_p_rx2_clk_fr_core,i_p_rx3_clk_fr_core,
    output o_p_pll_lock_0,o_p_rx_sigdet_sta_2,o_p_rx_sigdet_sta_3,
    output o_p_lx_cdr_align_2,o_p_lx_cdr_align_3,o_p_pcs_lsm_synced_2,o_p_pcs_lsm_synced_3,
    input i_p_l2rxn,i_p_l2rxp,i_p_l3rxn,i_p_l3rxp,
    output o_p_l2txn,o_p_l2txp,o_p_l3txn,o_p_l3txp,
    input [31:0] i_txd_2,i_txd_3,
    input [3:0] i_tdispsel_2,i_tdispctrl_2,i_txk_2,i_tdispsel_3,i_tdispctrl_3,i_txk_3,
    output [31:0] o_rxd_2,o_rxd_3,
    output [3:0] o_rdisper_2,o_rdecer_2,o_rdisper_3,o_rdecer_3,o_rxk_2,o_rxk_3,
    output [5:0] o_rxstatus_2,o_rxstatus_3,
    input i_pll_rst_0
);
    assign o_p_clk2core_tx_2=i_free_clk;
    assign o_p_pll_lock_0=1;
    assign o_txlane_done_2=1;
    assign o_txlane_done_3=1;
    assign o_p_rx_sigdet_sta_2=0;
    assign o_p_pcs_lsm_synced_2=0;
endmodule
