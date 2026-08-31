`timescale 1ns/1ps
`default_nettype none

/**
 * @file pcie_test_smoke_model.sv
 * @brief Controlled simulation boundary for the generated PCIe IP.
 *
 * This model supplies clocks, reset, and deterministic idle interfaces so the
 * project-owned top-level shell can be tested without the encrypted PCIe
 * protocol model. Model-driven link-up is an observation stimulus only; it
 * does not verify LTSSM, TLP, DMA, lane, reference-clock, or board behavior.
 */

/**
 * @brief Replace the generated `pcie_test` module for S2-A smoke simulation.
 *
 * Reset assertion is asynchronous through `core_rst_n`. Link indication is
 * released only after all three active-low reset inputs have remained high for
 * a fixed number of `pclk` cycles. All protocol outputs remain deterministic
 * and idle because this model has no PCIe transaction semantics.
 */
module pcie_test (
    output wire         pclk,
    output logic        pclk_div2,
    output wire         ref_clk,
    input  wire         ref_clk_n,
    input  wire         ref_clk_p,
    input  wire         button_rst_n,
    input  wire         power_up_rst_n,
    input  wire         perst_n,
    output wire         core_rst_n,
    input  wire         p_sel,
    input  wire [3:0]   p_strb,
    input  wire [15:0]  p_addr,
    input  wire [31:0]  p_wdata,
    input  wire         p_ce,
    input  wire         p_we,
    output wire         p_rdy,
    output wire [31:0]  p_rdata,
    input  wire [1:0]   rxn,
    input  wire [1:0]   rxp,
    output wire [1:0]   txn,
    output wire [1:0]   txp,
    input  wire [3:0]   pcs_nearend_loop,
    input  wire [3:0]   pma_nearend_ploop,
    input  wire [3:0]   pma_nearend_sloop,
    output wire         axis_master_tvalid,
    input  wire         axis_master_tready,
    output wire [127:0] axis_master_tdata,
    output wire [3:0]   axis_master_tkeep,
    output wire         axis_master_tlast,
    output wire [7:0]   axis_master_tuser,
    output wire         axis_slave0_tready,
    input  wire         axis_slave0_tvalid,
    input  wire [127:0] axis_slave0_tdata,
    input  wire         axis_slave0_tlast,
    input  wire         axis_slave0_tuser,
    output wire         axis_slave1_tready,
    input  wire         axis_slave1_tvalid,
    input  wire [127:0] axis_slave1_tdata,
    input  wire         axis_slave1_tlast,
    input  wire         axis_slave1_tuser,
    output wire         axis_slave2_tready,
    input  wire         axis_slave2_tvalid,
    input  wire [127:0] axis_slave2_tdata,
    input  wire         axis_slave2_tlast,
    input  wire         axis_slave2_tuser,
    output wire         pm_xtlh_block_tlp,
    output wire         cfg_send_cor_err_mux,
    output wire         cfg_send_nf_err_mux,
    output wire         cfg_send_f_err_mux,
    output wire         cfg_sys_err_rc,
    output wire         cfg_aer_rc_err_mux,
    output wire         radm_cpl_timeout,
    output wire [7:0]   cfg_pbus_num,
    output wire [4:0]   cfg_pbus_dev_num,
    output wire [2:0]   cfg_max_rd_req_size,
    output wire         cfg_bus_master_en,
    output wire [2:0]   cfg_max_payload_size,
    output wire         cfg_ext_tag_en,
    output wire         cfg_rcb,
    output wire         cfg_mem_space_en,
    output wire         cfg_pm_no_soft_rst,
    output wire         cfg_crs_sw_vis_en,
    output wire         cfg_no_snoop_en,
    output wire         cfg_relax_order_en,
    output wire [1:0]   cfg_tph_req_en,
    output wire [2:0]   cfg_pf_tph_st_mode,
    output wire         rbar_ctrl_update,
    output wire         cfg_atomic_req_en,
    output wire         radm_idle,
    output wire         radm_q_not_empty,
    output wire         radm_qoverflow,
    input  wire [1:0]   diag_ctrl_bus,
    output wire         cfg_link_auto_bw_mux,
    output wire         cfg_bw_mgt_mux,
    output wire         cfg_pme_mux,
    input  wire         app_ras_des_sd_hold_ltssm,
    input  wire [1:0]   app_ras_des_tba_ctrl,
    input  wire [3:0]   dyn_debug_info_sel,
    output wire [132:0] debug_info_mux,
    output logic        smlh_link_up,
    output logic        rdlh_link_up,
    output logic [4:0]  smlh_ltssm_state
);

    localparam logic [5:0] LINK_DELAY_LAST = 6'd31;

    logic [5:0] link_delay_count;

    assign ref_clk = ref_clk_p;
    assign pclk = ref_clk_p;
    assign core_rst_n = button_rst_n & power_up_rst_n & perst_n;

    assign p_rdy = 1'b0;
    assign p_rdata = 32'b0;
    assign txn = 2'b11;
    assign txp = 2'b00;

    assign axis_master_tvalid = 1'b0;
    assign axis_master_tdata = 128'b0;
    assign axis_master_tkeep = 4'b0;
    assign axis_master_tlast = 1'b0;
    assign axis_master_tuser = 8'b0;
    assign axis_slave0_tready = core_rst_n;
    assign axis_slave1_tready = core_rst_n;
    assign axis_slave2_tready = core_rst_n;

    assign pm_xtlh_block_tlp = 1'b0;
    assign cfg_send_cor_err_mux = 1'b0;
    assign cfg_send_nf_err_mux = 1'b0;
    assign cfg_send_f_err_mux = 1'b0;
    assign cfg_sys_err_rc = 1'b0;
    assign cfg_aer_rc_err_mux = 1'b0;
    assign radm_cpl_timeout = 1'b0;
    assign cfg_pbus_num = 8'b0;
    assign cfg_pbus_dev_num = 5'b0;
    assign cfg_max_rd_req_size = 3'd2;
    assign cfg_bus_master_en = 1'b0;
    assign cfg_max_payload_size = 3'd0;
    assign cfg_ext_tag_en = 1'b0;
    assign cfg_rcb = 1'b0;
    assign cfg_mem_space_en = 1'b0;
    assign cfg_pm_no_soft_rst = 1'b0;
    assign cfg_crs_sw_vis_en = 1'b0;
    assign cfg_no_snoop_en = 1'b0;
    assign cfg_relax_order_en = 1'b0;
    assign cfg_tph_req_en = 2'b0;
    assign cfg_pf_tph_st_mode = 3'b0;
    assign rbar_ctrl_update = 1'b0;
    assign cfg_atomic_req_en = 1'b0;
    assign radm_idle = 1'b1;
    assign radm_q_not_empty = 1'b0;
    assign radm_qoverflow = 1'b0;
    assign cfg_link_auto_bw_mux = 1'b0;
    assign cfg_bw_mgt_mux = 1'b0;
    assign cfg_pme_mux = 1'b0;
    assign debug_info_mux = 133'b0;

    // The divided clock is deterministic but is not frequency-accurate to the
    // generated PCIe IP. S2-A checks reset ownership, not clock performance.
    always_ff @(posedge ref_clk_p or negedge core_rst_n) begin
        if (!core_rst_n) begin
            pclk_div2 <= 1'b0;
        end else begin
            pclk_div2 <= ~pclk_div2;
        end
    end

    // Link indication is delayed so the testbench can observe the reset-to-idle
    // interval. It is stimulus generated by this model, not protocol evidence.
    always_ff @(posedge pclk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            link_delay_count <= 6'b0;
            smlh_link_up <= 1'b0;
            rdlh_link_up <= 1'b0;
            smlh_ltssm_state <= 5'b0;
        end else if (link_delay_count == LINK_DELAY_LAST) begin
            smlh_link_up <= 1'b1;
            rdlh_link_up <= 1'b1;
            smlh_ltssm_state <= 5'h11;
        end else begin
            link_delay_count <= link_delay_count + 6'd1;
        end
    end

endmodule

`default_nettype wire
