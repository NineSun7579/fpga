// PCIe endpoint and DMA data source for the camera frame path.
`include "rtl/pcie_dma_ctrl/ips2l_pcie_dma_wr_ctrl.v"
`include "rtl/pcie_dma_ctrl/ips2l_pcie_dma_tx_cpld_rd_ctrl.v"
module camera_pcie_dma (
    input         button_rst_n,
    input         ref_clk_p,
    input         ref_clk_n,
    input         perst_n,
    input  [1:0]  rxn,
    input  [1:0]  rxp,
    output [1:0]  txn,
    output [1:0]  txp,
    output reg    ref_led,
    output reg    pclk_led,
    output        rd_clk,
    output        rd_rst_n,
    input         rd_fifo_empty,
    input  [15:0] rd_fifo_data,
    output        rd_fifo_rd_en,
    output        bar0_rd_clk_en,
    output [11:0] bar0_rd_addr
);
    wire pclk;
    wire pclk_div2;
    wire ref_clk;
    wire core_rst_n;
    wire sync_button_rst_n;
    wire sync_perst_n;
    wire ref_core_rst_n;
    wire pclk_core_rst_n;
    wire pcie_axis_master_tvalid;
    wire pcie_axis_master_tready;
    wire [127:0] pcie_axis_master_tdata;
    wire [3:0] pcie_axis_master_tkeep;
    wire pcie_axis_master_tlast;
    wire [7:0] pcie_axis_master_tuser;
    wire dma_axis0_tvalid;
    wire dma_axis0_tready;
    wire [127:0] dma_axis0_tdata;
    wire dma_axis0_tlast;
    wire dma_axis0_tuser;
    wire axis_slave1_tready;
    wire axis_slave1_tvalid;
    wire [127:0] axis_slave1_tdata;
    wire axis_slave1_tlast;
    wire axis_slave1_tuser;
    wire axis_slave2_tready;
    wire axis_slave2_tvalid;
    wire [127:0] axis_slave2_tdata;
    wire axis_slave2_tlast;
    wire axis_slave2_tuser;
    wire [7:0] cfg_pbus_num;
    wire [4:0] cfg_pbus_dev_num;
    wire [2:0] cfg_max_rd_req_size;
    wire [2:0] cfg_max_payload_size;
    wire cfg_ido_req_en = 1'b0;
    wire cfg_ido_cpl_en = 1'b0;
    wire [7:0] xadm_ph_cdts = 8'd0;
    wire [11:0] xadm_pd_cdts = 12'd0;
    wire [7:0] xadm_nph_cdts = 8'd0;
    wire [11:0] xadm_npd_cdts = 12'd0;
    wire [7:0] xadm_cplh_cdts = 8'd0;
    wire [11:0] xadm_cpld_cdts = 12'd0;
    wire [2:0] trgt_radm_pkt_halt;
    wire [31:0] dma_apb_rdata;
    wire dma_apb_ready;
    wire [15:0] pcie_apb_addr;
    wire [31:0] pcie_apb_wdata;
    wire [3:0] pcie_apb_strb;
    wire pcie_apb_sel;
    wire pcie_apb_ce;
    wire pcie_apb_we;
    wire pcie_apb_ready;
    wire [31:0] pcie_apb_rdata;
    wire [11:0] dma_bar0_addr;
    wire dma_bar0_en;
    wire smlh_link_up;
    wire rdlh_link_up;
    reg [127:0] frame_word;
    reg [2:0] frame_half_count;
    reg frame_word_valid;
    reg [22:0] ref_led_cnt;
    reg [26:0] pclk_led_cnt;

    assign rd_clk = pclk_div2;
    assign rd_rst_n = core_rst_n;
    assign bar0_rd_clk_en = dma_bar0_en;
    assign bar0_rd_addr = dma_bar0_addr;
    assign rd_fifo_rd_en = !rd_fifo_empty && !frame_word_valid;
    assign axis_slave1_tvalid = 1'b0;
    assign axis_slave1_tdata = 128'd0;
    assign axis_slave1_tlast = 1'b0;
    assign axis_slave1_tuser = 1'b0;
    assign axis_slave2_tvalid = 1'b0;
    assign axis_slave2_tdata = 128'd0;
    assign axis_slave2_tlast = 1'b0;
    assign axis_slave2_tuser = 1'b0;

    always @(posedge pclk_div2 or negedge core_rst_n) begin
        if (!core_rst_n) begin
            frame_word       <= 128'd0;
            frame_half_count <= 3'd0;
            frame_word_valid <= 1'b0;
        end else begin
            if (frame_word_valid && dma_bar0_en)
                frame_word_valid <= 1'b0;
            if (!rd_fifo_empty && !frame_word_valid) begin
                frame_word <= {frame_word[111:0], rd_fifo_data};
                if (frame_half_count == 3'd7) begin
                    frame_half_count <= 3'd0;
                    frame_word_valid <= 1'b1;
                end else begin
                    frame_half_count <= frame_half_count + 1'b1;
                end
            end
        end
    end

    always @(posedge ref_clk or negedge sync_perst_n) begin
        if (!sync_perst_n) begin
            ref_led_cnt <= 23'd0;
            ref_led <= 1'b1;
        end else if (smlh_link_up && rdlh_link_up) begin
            ref_led_cnt <= ref_led_cnt + 1'b1;
            if (&ref_led_cnt)
                ref_led <= ~ref_led;
        end
    end

    always @(posedge pclk or negedge pclk_core_rst_n) begin
        if (!pclk_core_rst_n) begin
            pclk_led_cnt <= 27'd0;
            pclk_led <= 1'b1;
        end else if (smlh_link_up && rdlh_link_up) begin
            pclk_led_cnt <= pclk_led_cnt + 1'b1;
            if (&pclk_led_cnt)
                pclk_led <= ~pclk_led;
        end
    end

    hsst_rst_cross_sync_v1_0 #(.RST_CNTR_VALUE(16'hC000)) u_button_rst (
        .clk(ref_clk), .rstn_in(button_rst_n), .rstn_out(sync_button_rst_n)
    );
    hsst_rst_cross_sync_v1_0 #(.RST_CNTR_VALUE(16'hC000)) u_perst (
        .clk(ref_clk), .rstn_in(perst_n), .rstn_out(sync_perst_n)
    );

    hsst_rst_sync_v1_0 u_pclk_core_rstn_sync (
        .clk(pclk),
        .rst_n(core_rst_n),
        .sig_async(1'b1),
        .sig_synced(pclk_core_rst_n)
    );

    pcie_test u_pcie (
        .pclk(pclk), .pclk_div2(pclk_div2), .ref_clk(ref_clk),
        .ref_clk_n(ref_clk_n), .ref_clk_p(ref_clk_p),
        .button_rst_n(sync_button_rst_n), .power_up_rst_n(sync_perst_n),
        .perst_n(sync_perst_n), .core_rst_n(core_rst_n),
        .p_sel(pcie_apb_sel), .p_strb(pcie_apb_strb), .p_addr(pcie_apb_addr),
        .p_wdata(pcie_apb_wdata), .p_ce(pcie_apb_ce), .p_we(pcie_apb_we),
        .p_rdy(pcie_apb_ready), .p_rdata(pcie_apb_rdata),
        .rxn(rxn), .rxp(rxp), .txn(txn), .txp(txp),
        .pcs_nearend_loop(2'd0), .pma_nearend_ploop(2'd0), .pma_nearend_sloop(2'd0),
        .axis_master_tvalid(pcie_axis_master_tvalid),
        .axis_master_tready(pcie_axis_master_tready),
        .axis_master_tdata(pcie_axis_master_tdata),
        .axis_master_tkeep(pcie_axis_master_tkeep),
        .axis_master_tlast(pcie_axis_master_tlast),
        .axis_master_tuser(pcie_axis_master_tuser),
        .axis_slave0_tready(dma_axis0_tready), .axis_slave0_tvalid(dma_axis0_tvalid),
        .axis_slave0_tdata(dma_axis0_tdata), .axis_slave0_tlast(dma_axis0_tlast),
        .axis_slave0_tuser(dma_axis0_tuser),
        .axis_slave1_tready(axis_slave1_tready), .axis_slave1_tvalid(axis_slave1_tvalid),
        .axis_slave1_tdata(axis_slave1_tdata), .axis_slave1_tlast(axis_slave1_tlast), .axis_slave1_tuser(axis_slave1_tuser),
        .axis_slave2_tready(axis_slave2_tready), .axis_slave2_tvalid(axis_slave2_tvalid),
        .axis_slave2_tdata(axis_slave2_tdata), .axis_slave2_tlast(axis_slave2_tlast), .axis_slave2_tuser(axis_slave2_tuser),
        .pm_xtlh_block_tlp(), .cfg_send_cor_err_mux(), .cfg_send_nf_err_mux(),
        .cfg_send_f_err_mux(), .cfg_sys_err_rc(), .cfg_aer_rc_err_mux(),
        .radm_cpl_timeout(), .cfg_pbus_num(cfg_pbus_num),
        .cfg_pbus_dev_num(cfg_pbus_dev_num), .cfg_max_rd_req_size(cfg_max_rd_req_size),
        .cfg_bus_master_en(), .cfg_max_payload_size(cfg_max_payload_size),
        .cfg_ext_tag_en(), .cfg_rcb(), .cfg_mem_space_en(), .cfg_pm_no_soft_rst(),
        .cfg_crs_sw_vis_en(), .cfg_no_snoop_en(), .cfg_relax_order_en(),
        .cfg_tph_req_en(), .cfg_pf_tph_st_mode(), .rbar_ctrl_update(),
        .cfg_atomic_req_en(), .radm_idle(), .radm_q_not_empty(), .radm_qoverflow(),
        .diag_ctrl_bus(2'd0), .cfg_link_auto_bw_mux(), .cfg_bw_mgt_mux(), .cfg_pme_mux(),
        .app_ras_des_sd_hold_ltssm(1'b0), .app_ras_des_tba_ctrl(2'd0),
         .dyn_debug_info_sel(4'd0), .debug_info_mux(), .smlh_link_up(smlh_link_up),
         .rdlh_link_up(rdlh_link_up), .smlh_ltssm_state()
    );

    ips2l_pcie_dma #(.DEVICE_TYPE(3'd0), .AXIS_SLAVE_NUM(1)) u_dma (
        .clk(pclk_div2), .rst_n(core_rst_n),
        .i_cfg_pbus_num(cfg_pbus_num), .i_cfg_pbus_dev_num(cfg_pbus_dev_num),
        .i_cfg_max_rd_req_size(cfg_max_rd_req_size),
        .i_cfg_max_payload_size(cfg_max_payload_size),
        .i_axis_master_tvld(pcie_axis_master_tvalid),
        .o_axis_master_trdy(pcie_axis_master_tready),
        .i_axis_master_tdata(pcie_axis_master_tdata),
        .i_axis_master_tkeep(pcie_axis_master_tkeep),
        .i_axis_master_tlast(pcie_axis_master_tlast),
        .i_axis_master_tuser(pcie_axis_master_tuser),
        .o_trgt1_radm_pkt_halt(trgt_radm_pkt_halt),
        .i_axis_slave0_trdy(dma_axis0_tready), .o_axis_slave0_tvld(dma_axis0_tvalid),
        .o_axis_slave0_tdata(dma_axis0_tdata), .o_axis_slave0_tlast(dma_axis0_tlast),
        .o_axis_slave0_tuser(dma_axis0_tuser),
        .i_axis_slave1_trdy(axis_slave1_tready), .i_axis_slave2_trdy(axis_slave2_tready),
        .i_cfg_ido_req_en(cfg_ido_req_en), .i_cfg_ido_cpl_en(cfg_ido_cpl_en),
        .i_xadm_ph_cdts(xadm_ph_cdts), .i_xadm_pd_cdts(xadm_pd_cdts),
        .i_xadm_nph_cdts(xadm_nph_cdts), .i_xadm_npd_cdts(xadm_npd_cdts),
        .i_xadm_cplh_cdts(xadm_cplh_cdts), .i_xadm_cpld_cdts(xadm_cpld_cdts),
        .i_apb_psel(1'b0), .i_apb_paddr(9'd0), .i_apb_pwdata(32'd0),
        .i_apb_pstrb(4'd0), .i_apb_pwrite(1'b0), .i_apb_penable(1'b0),
        .o_apb_prdy(dma_apb_ready), .o_apb_prdata(dma_apb_rdata),
        .o_cross_4kb_boundary(), .o_bar0_rd_clk_en(dma_bar0_en),
        .o_bar0_rd_addr(dma_bar0_addr), .i_bar0_rd_data(frame_word)
    );
    assign pcie_apb_sel = 1'b0;
    assign pcie_apb_strb = 4'd0;
    assign pcie_apb_addr = 16'd0;
    assign pcie_apb_wdata = 32'd0;
    assign pcie_apb_ce = 1'b0;
    assign pcie_apb_we = 1'b0;
endmodule

module camera_async_fifo_256 (
    input wr_clk, input wr_rst_n, input wr_en, input [255:0] wr_data, output wr_full,
    input rd_clk, input rd_rst_n, input rd_en, output [255:0] rd_data, output rd_empty
);
    reg [255:0] mem [0:15];
    reg [4:0] wr_bin, rd_bin;
    reg [4:0] wr_gray, rd_gray;
    reg [4:0] rd_gray_w1, rd_gray_w2, wr_gray_r1, wr_gray_r2;
    wire full_i = (wr_gray == {~rd_gray_w2[4:3], rd_gray_w2[2:0]});
    wire empty_i = (rd_gray == wr_gray_r2);
    assign wr_full = full_i;
    assign rd_empty = empty_i;
    assign rd_data = mem[rd_bin[3:0]];
    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin wr_bin <= 0; wr_gray <= 0; rd_gray_w1 <= 0; rd_gray_w2 <= 0; end
        else begin
            rd_gray_w1 <= rd_gray; rd_gray_w2 <= rd_gray_w1;
            if (wr_en && !full_i) mem[wr_bin[3:0]] <= wr_data;
            if (wr_en && !full_i) begin wr_bin <= wr_bin + 1'b1; wr_gray <= ((wr_bin + 1'b1) >> 1) ^ (wr_bin + 1'b1); end
        end
    end
    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin rd_bin <= 0; rd_gray <= 0; wr_gray_r1 <= 0; wr_gray_r2 <= 0; end
        else begin
            wr_gray_r1 <= wr_gray; wr_gray_r2 <= wr_gray_r1;
            if (rd_en && !empty_i) begin rd_bin <= rd_bin + 1'b1; rd_gray <= ((rd_bin + 1'b1) >> 1) ^ (rd_bin + 1'b1); end
        end
    end
endmodule
