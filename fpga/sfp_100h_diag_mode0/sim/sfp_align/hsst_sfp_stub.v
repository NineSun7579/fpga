`timescale 1ns/1ps
// Only the ports connected by the unmodified production sfp_rx_link.
// No analog, PCS, FIFO occupancy, or vendor primitive behavior is modeled.
module hsst_sfp (
 input i_free_clk, i_p_refckn_0, i_p_refckp_0,
 input i_wtchdg_clr_0, i_wtchdg_clr_1, i_pll_rst_0, i_pll_rst_1,
 input i_p_tx2_clk_fr_core, i_p_tx3_clk_fr_core,
 input i_p_rx2_clk_fr_core, i_p_rx3_clk_fr_core,
 input i_p_l2rxn, i_p_l2rxp, i_p_l3rxn, i_p_l3rxp,
 input [31:0] i_txd_2,
 input [3:0] i_tdispsel_2, i_tdispctrl_2, i_txk_2,
 output [1:0] o_wtchdg_st_0, o_wtchdg_st_1,
 output o_pll_done_0, o_pll_done_1, o_txlane_done_2, o_rxlane_done_2,
 output o_p_clk2core_tx_2, o_p_clk2core_rx_2,
 output o_p_pll_lock_0, o_p_pll_lock_1,
 output o_p_rx_sigdet_sta_2, o_p_lx_cdr_align_2, o_p_pcs_lsm_synced_2,
 output o_p_l2txn, o_p_l2txp, o_p_l3txn, o_p_l3txp,
 output [2:0] o_rxstatus_2,
 output [31:0] o_rxd_2,
 output [3:0] o_rdisper_2, o_rdecer_2, o_rxk_2
);
 reg clk = 0;
 always #4 clk = ~clk;
 reg lane_done = 0;
 reg [31:0] drive_d = 32'hBC0028BC;
 reg [3:0] drive_k = 4'b1001;
 assign o_p_clk2core_tx_2 = clk;
 assign o_p_clk2core_rx_2 = clk;
 assign o_rxd_2 = drive_d;
 assign o_rxk_2 = drive_k;
 assign o_rxlane_done_2 = lane_done;
 assign o_txlane_done_2 = lane_done;
 assign o_p_pcs_lsm_synced_2 = lane_done;
 assign o_p_pll_lock_0 = 1;
 assign o_p_pll_lock_1 = 1;
 assign o_p_rx_sigdet_sta_2 = 1;
 assign o_p_lx_cdr_align_2 = 1;
 assign o_wtchdg_st_0 = 0;
 assign o_wtchdg_st_1 = 0;
 assign o_pll_done_0 = 1;
 assign o_pll_done_1 = 1;
 assign o_rxstatus_2 = 0;
 assign o_rdisper_2 = 0;
 assign o_rdecer_2 = 0;
 assign o_p_l2txn = 0;
 assign o_p_l2txp = 0;
 assign o_p_l3txn = 0;
 assign o_p_l3txp = 0;
endmodule
