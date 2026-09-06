`timescale 1ns/1ps

// Minimal bring-up top for the PG2L100H-6FBG484 target.
// OV5640 DVP capture and DDR3 frame write top.
module camera_ddr3_test_top (
    input        sys_clk,
    input        button_rst_n,
    input        ref_clk_p,
    input        ref_clk_n,
    input        perst_n,
    input  [1:0]  rxn,
    input  [1:0]  rxp,
    output [1:0]  txn,
    output [1:0]  txp,
    output        ref_led,
    output        pclk_led,

    input        cam_pclk,
    input        cam_vsync,
    input        cam_href,
    input  [7:0] cam_data,
    output       cam_rst_n,
    output       cam_pwdn,
    output       cam_scl,
    inout        cam_sda,
    output       mem_rst_n,
    output       mem_ck,
    output       mem_ck_n,
    output       mem_cke,
    output       mem_ras_n,
    output       mem_cas_n,
    output       mem_we_n,
    output       mem_odt,
    output       mem_cs_n,
    output [14:0] mem_a,
    output [2:0]  mem_ba,
    inout  [1:0]  mem_dqs,
    inout  [1:0]  mem_dqs_n,
    inout  [15:0] mem_dq,
    output [1:0]  mem_dm
);

    wire        cam_init_done;
    wire        cam_i2c_ack;
    wire        cam_frame_vsync;
    wire        cam_frame_href;
    wire        cam_frame_valid;
    wire [15:0] cam_frame_data;

    ov5640_dri #(
        // sys_clk is the FPGA-side 25 MHz clock used by the I2C driver.
        // The OV5640 module uses its own 24 MHz crystal for the camera PLL.
        .CLK_FREQ         (27'd25_000_000)
    ) u_ov5640_dri (
        .clk              (sys_clk),
         .rst_n            (button_rst_n),
        .cam_pclk         (cam_pclk),
        .cam_vsync        (cam_vsync),
        .cam_href         (cam_href),
        .cam_data         (cam_data),
        .cam_rst_n        (cam_rst_n),
        .cam_pwdn         (cam_pwdn),
        .cam_scl          (cam_scl),
        .cam_sda          (cam_sda),
        .cmos_h_pixel     (13'd640),    //horizon pixel
        .cmos_v_pixel     (13'd480),    //vertical pixel
        .total_h_pixel    (13'd1650),   //FPS = PCLK / (total_h_pixel * total_v_pixel)
        .total_v_pixel    (13'd750),
        .capture_start    (cam_init_done),
        .cam_init_done    (cam_init_done),
        .cam_i2c_ack      (cam_i2c_ack),
        .cmos_frame_vsync (cam_frame_vsync),
        .cmos_frame_href  (cam_frame_href),
        .cmos_frame_valid (cam_frame_valid),
        .cmos_frame_data  (cam_frame_data)
    );

    wire        ddr_core_clk;
    wire        ddr_pll_lock;
    wire        ddr_phy_pll_lock;
    wire        ddr_gpll_lock;
    wire        ddr_rst_gpll_lock;
    wire        ddr_cpd_lock;
    wire        ddr_init_done;

    reg  [27:0] axi_awaddr;
    reg         axi_awuser_ap;
    reg  [3:0]  axi_awuser_id;
    reg  [3:0]  axi_awlen;
    wire        axi_awready;
    reg         axi_awvalid;

    reg  [127:0] axi_wdata;
    reg  [15:0]  axi_wstrb;
    wire         axi_wready;
    wire [3:0]   axi_wusero_id;
    wire         axi_wusero_last;

    reg  [27:0] axi_araddr;
    reg         axi_aruser_ap;
    reg  [3:0]  axi_aruser_id;
    reg  [3:0]  axi_arlen;
    wire        axi_arready;
    reg         axi_arvalid;

    wire [127:0] axi_rdata;
    wire [3:0]   axi_rid;
    wire         axi_rlast;
    wire         axi_rvalid;

    wire         apb_ready;
    wire [15:0]  apb_rdata;

    wire [33:0]  debug_calib_ctrl;
    wire [33:0]  dbg_slice_status;
    wire [43:0]  dbg_slice_state;
    wire [137:0] debug_data;
    wire [1:0]   dbg_dll_upd_state;
    wire [8:0]   debug_gpll_dps_phase;
    wire [2:0]   dbg_rst_dps_state;
    wire [5:0]   dbg_tran_err_rst_cnt;
    wire         dbg_ddrphy_init_fail;
    wire [9:0]   debug_dps_cnt_dir0;
    wire [9:0]   debug_dps_cnt_dir1;
    wire [7:0]   ck_dly_set_bin;
    wire [3:0]   debug_rst_state;
    wire [3:0]   debug_cpd_state;

    localparam FRAME_WORDS = 19'd153600;    // width * height / 2
    localparam FRAME_BYTES = 28'd614400;    // width * height * 2

    wire [255:0] wr_fifo_data;
    wire         wr_fifo_empty;
    wire         wr_fifo_full;
    wire         wr_fifo_rd_en;
    wire [14:0]  wr_fifo_wlevel;
    wire [10:0]  wr_fifo_rlevel;
    wire [15:0]  wr_fifo_unused_level;
    wire         wr_fifo_almost_full;
    wire         wr_fifo_almost_empty;

    wire [255:0] cam_bridge_data;
    wire         cam_bridge_empty;
    wire         cam_bridge_full;
    wire         cam_bridge_rd_en;
    wire [127:0] ddr_read_data;
    reg          ddr_read_valid;
    wire         ddr_read_last;

    wire [15:0]  rd_fifo_data;
    wire         rd_fifo_empty;
    wire         rd_fifo_full;
    wire         rd_fifo_wr_en;
    wire         rd_fifo_rd_en;
    wire         pcie_clk;
    wire         pcie_rst_n;
    wire         pcie_bar0_rd_en;
    wire [11:0]  pcie_bar0_rd_addr;
    wire         pcie_axis_slave0_tready;
    wire         pcie_axis_slave0_tvalid;
    wire [127:0] pcie_axis_slave0_tdata;
    wire         pcie_axis_slave0_tlast;
    wire         pcie_axis_slave0_tuser;

    reg  [15:0] camera_pixel_data;
    reg         camera_pixel_valid;
    reg  [255:0] ddr_write_data;
    reg  [27:0] ddr_write_addr;
    reg  [27:0] ddr_read_addr;
    reg  [18:0] ddr_write_count;
    reg  [18:0] ddr_read_count;
    reg         frame_ready;
    reg         ddr_write_active;
    reg         ddr_read_active;
    reg         ddr_write_phase;
    reg         ddr_read_phase;

    always @(posedge cam_pclk or negedge button_rst_n) begin
         if (!button_rst_n) begin
            camera_pixel_data  <= 16'd0;
            camera_pixel_valid <= 1'b0;
        end else begin
            camera_pixel_valid <= cam_init_done && cam_frame_href && cam_frame_valid;
            camera_pixel_data  <= cam_frame_data;
        end
    end

    wr_fifo u_wr_fifo (
        .clk              (cam_pclk),
         .rst              (!button_rst_n),
        .wr_en            (camera_pixel_valid && !wr_fifo_full),
        .wr_data          (camera_pixel_data),
        .wr_full          (wr_fifo_full),
        .wr_water_level   (wr_fifo_wlevel),
        .almost_full      (wr_fifo_almost_full),
        .rd_en            (wr_fifo_rd_en),
        .rd_data          (wr_fifo_data),
        .rd_empty         (wr_fifo_empty),
        .rd_water_level   (wr_fifo_rlevel),
        .almost_empty     (wr_fifo_almost_empty)
    );

    // wr_fifo is the camera-side packing FIFO. This bridge makes its 256-bit
    // output safe for the DDR clock domain because wr_fifo itself is synchronous.
    camera_async_fifo_256 u_camera_ddr_bridge (
        .wr_clk           (cam_pclk),
         .wr_rst_n         (button_rst_n),
        .wr_en            (!wr_fifo_empty && !cam_bridge_full),
        .wr_data          (wr_fifo_data),
        .wr_full          (cam_bridge_full),
        .rd_clk           (ddr_core_clk),
         .rd_rst_n         (button_rst_n),
        .rd_en            (cam_bridge_rd_en),
        .rd_data          (cam_bridge_data),
        .rd_empty         (cam_bridge_empty)
    );

    DDR3 u_ddr3 (
        .ref_clk                  (sys_clk),
        .resetn                   (button_rst_n),
        .core_clk                 (ddr_core_clk),
        .pll_lock                 (ddr_pll_lock),
        .phy_pll_lock             (ddr_phy_pll_lock),
        .gpll_lock                (ddr_gpll_lock),
        .rst_gpll_lock            (ddr_rst_gpll_lock),
        .ddrphy_cpd_lock          (ddr_cpd_lock),
        .ddr_init_done             (ddr_init_done),
        .axi_awaddr               (axi_awaddr),
        .axi_awuser_ap            (axi_awuser_ap),
        .axi_awuser_id            (axi_awuser_id),
        .axi_awlen                (axi_awlen),
        .axi_awready              (axi_awready),
        .axi_awvalid              (axi_awvalid),
        .axi_wdata                (axi_wdata),
        .axi_wstrb                (axi_wstrb),
        .axi_wready               (axi_wready),
        .axi_wusero_id            (axi_wusero_id),
        .axi_wusero_last          (axi_wusero_last),
        .axi_araddr               (axi_araddr),
        .axi_aruser_ap            (axi_aruser_ap),
        .axi_aruser_id            (axi_aruser_id),
        .axi_arlen                (axi_arlen),
        .axi_arready              (axi_arready),
        .axi_arvalid              (axi_arvalid),
        .axi_rdata                (axi_rdata),
        .axi_rid                  (axi_rid),
        .axi_rlast                (axi_rlast),
        .axi_rvalid               (axi_rvalid),
        .apb_clk                  (sys_clk),
        .apb_rst_n                (button_rst_n),
        .apb_sel                  (1'b0),
        .apb_enable               (1'b0),
        .apb_addr                 (8'd0),
        .apb_write                (1'b0),
        .apb_ready                (apb_ready),
        .apb_wdata                (16'd0),
        .apb_rdata                (apb_rdata),
        .mem_cs_n                 (mem_cs_n),
        .mem_rst_n                (mem_rst_n),
        .mem_ck                   (mem_ck),
        .mem_ck_n                 (mem_ck_n),
        .mem_cke                 (mem_cke),
        .mem_ras_n                (mem_ras_n),
        .mem_cas_n                (mem_cas_n),
        .mem_we_n                 (mem_we_n),
        .mem_odt                  (mem_odt),
        .mem_a                    (mem_a),
        .mem_ba                   (mem_ba),
        .mem_dqs                  (mem_dqs),
        .mem_dqs_n                (mem_dqs_n),
        .mem_dq                   (mem_dq),
        .mem_dm                   (mem_dm),
        .dbg_gate_start           (1'b0),
        .dbg_cpd_start            (1'b0),
        .dbg_ddrphy_rst_n         (1'b1),
        .dbg_gpll_scan_rst        (1'b0),
        .samp_position_dyn_adj    (1'b0),
        .init_samp_position_even  (16'd0),
        .init_samp_position_odd   (16'd0),
        .wrcal_position_dyn_adj   (1'b0),
        .init_wrcal_position      (16'd0),
        .force_read_clk_ctrl      (1'b0),
        .init_slip_step           (8'd0),
        .init_read_clk_ctrl       (6'd0),
        .debug_calib_ctrl         (debug_calib_ctrl),
        .dbg_slice_status         (dbg_slice_status),
        .dbg_slice_state          (dbg_slice_state),
        .debug_data               (debug_data),
        .dbg_dll_upd_state        (dbg_dll_upd_state),
        .debug_gpll_dps_phase     (debug_gpll_dps_phase),
        .dbg_rst_dps_state        (dbg_rst_dps_state),
        .dbg_tran_err_rst_cnt     (dbg_tran_err_rst_cnt),
        .dbg_ddrphy_init_fail     (dbg_ddrphy_init_fail),
        .debug_cpd_offset_adj     (1'b0),
        .debug_cpd_offset_dir     (1'b0),
        .debug_cpd_offset         (10'd0),
        .debug_dps_cnt_dir0       (debug_dps_cnt_dir0),
        .debug_dps_cnt_dir1       (debug_dps_cnt_dir1),
        .ck_dly_en                (1'b0),
        .init_ck_dly_step         (8'd0),
        .ck_dly_set_bin           (ck_dly_set_bin),
        .align_error              (),
        .debug_rst_state          (debug_rst_state),
        .debug_cpd_state          (debug_cpd_state)
    );

    assign wr_fifo_rd_en = !wr_fifo_empty && !cam_bridge_full;
    assign cam_bridge_rd_en = !cam_bridge_empty && !ddr_write_active;
    assign rd_fifo_wr_en = ddr_read_valid && !rd_fifo_full;

    // DDR3 uses two 128-bit beats for each 256-bit FIFO word. Reads are
    // started only after a complete frame is stored in the frame buffer.
    always @(posedge ddr_core_clk or negedge button_rst_n) begin
         if (!button_rst_n) begin
            axi_awaddr      <= 28'd0;
            axi_awuser_ap   <= 1'b0;
            axi_awuser_id   <= 4'd0;
            axi_awlen       <= 4'd0;
            axi_awvalid     <= 1'b0;
            axi_wdata       <= 128'd0;
            axi_wstrb       <= 16'hFFFF;
            axi_araddr      <= 28'd0;
            axi_aruser_ap   <= 1'b0;
            axi_aruser_id   <= 4'd0;
            axi_arlen       <= 4'd0;
            axi_arvalid     <= 1'b0;
            ddr_write_data  <= 256'd0;
            ddr_write_addr  <= 28'd0;
            ddr_read_addr   <= 28'd0;
            ddr_write_count <= 19'd0;
            ddr_read_count  <= 19'd0;
            frame_ready     <= 1'b0;
            ddr_write_active <= 1'b0;
            ddr_read_active  <= 1'b0;
            ddr_write_phase  <= 1'b0;
            ddr_read_phase   <= 1'b0;
            ddr_read_valid  <= 1'b0;
        end else begin
            ddr_read_valid <= 1'b0;
            if (ddr_init_done && !frame_ready && !ddr_write_active && !cam_bridge_empty) begin
                ddr_write_active <= 1'b1;
                ddr_write_data   <= cam_bridge_data;
            end

            if (ddr_write_active) begin
                if (!ddr_write_phase) begin
                    axi_awaddr  <= ddr_write_addr;
                    axi_awvalid <= 1'b1;
                    axi_wdata   <= cam_bridge_data[127:0];
                    if (axi_awready) begin
                        axi_awvalid    <= 1'b0;
                        ddr_write_phase <= 1'b1;
                    end
                end else if (axi_wready) begin
                    axi_wdata      <= ddr_write_data[255:128];
                    ddr_write_addr <= ddr_write_addr + 28'd32;
                    ddr_write_phase <= 1'b0;
                    if (ddr_write_count == FRAME_WORDS - 1'b1) begin
                        ddr_write_count  <= 19'd0;
                        ddr_write_active <= 1'b0;
                        frame_ready      <= 1'b1;
                        ddr_read_addr    <= 28'd0;
                        ddr_read_count   <= 19'd0;
                    end else begin
                        ddr_write_count <= ddr_write_count + 1'b1;
                    end
                end
            end

            if (frame_ready && !ddr_read_active && !rd_fifo_full) begin
                ddr_read_active <= 1'b1;
                axi_araddr      <= ddr_read_addr;
                axi_arvalid     <= 1'b1;
            end
            if (ddr_read_active && axi_arready) begin
                axi_arvalid    <= 1'b0;
                ddr_read_active <= 1'b0;
            end
            if (axi_rvalid) begin
                if (!ddr_read_phase) begin
                    ddr_write_data[127:0] <= axi_rdata;
                    ddr_read_phase <= 1'b1;
                end else if (!rd_fifo_full) begin
                    ddr_write_data[255:128] <= axi_rdata;
                    ddr_read_valid <= 1'b1;
                    ddr_read_phase <= 1'b0;
                    ddr_read_addr <= ddr_read_addr + 28'd32;
                    if (ddr_read_count == FRAME_WORDS - 1'b1) begin
                        ddr_read_count <= 19'd0;
                        ddr_read_addr  <= 28'd0;
                    end else begin
                        ddr_read_count <= ddr_read_count + 1'b1;
                    end
                end
            end
        end
    end

    rd_fifo u_rd_fifo (
        .wr_clk           (ddr_core_clk),
         .wr_rst           (!button_rst_n),
        .wr_en            (rd_fifo_wr_en),
        .wr_data          (ddr_write_data),
        .wr_full          (rd_fifo_full),
        .wr_water_level   (),
        .almost_full      (),
        .rd_clk           (pcie_clk),
        .rd_rst           (!pcie_rst_n),
        .rd_en            (rd_fifo_rd_en),
        .rd_data          (rd_fifo_data),
        .rd_empty         (rd_fifo_empty),
        .rd_water_level   (),
        .almost_empty     ()
    );

    camera_pcie_dma u_camera_pcie_dma (
        .button_rst_n           (button_rst_n),
        .ref_clk_p              (ref_clk_p),
        .ref_clk_n              (ref_clk_n),
        .perst_n                (perst_n),
        .rxn                    (rxn),
        .rxp                    (rxp),
        .txn                    (txn),
         .txp                    (txp),
         .ref_led               (ref_led),
         .pclk_led              (pclk_led),
         .rd_clk                (pcie_clk),
        .rd_rst_n               (pcie_rst_n),
        .rd_fifo_empty          (rd_fifo_empty),
        .rd_fifo_data           (rd_fifo_data),
        .rd_fifo_rd_en          (rd_fifo_rd_en),
        .bar0_rd_clk_en         (pcie_bar0_rd_en),
         .bar0_rd_addr           (pcie_bar0_rd_addr),
         .dbg_cam_init_done      (cam_init_done),
         .dbg_cam_frame_valid    (cam_frame_valid),
         .dbg_camera_pixel_valid (camera_pixel_valid),
         .dbg_cam_pclk           (cam_pclk),
         .dbg_cam_href           (cam_href),
         .dbg_cam_vsync          (cam_vsync),
         .dbg_cam_data           (cam_data),
         .dbg_wr_fifo_empty      (wr_fifo_empty),
         .dbg_wr_fifo_full       (wr_fifo_full),
         .dbg_cam_bridge_empty   (cam_bridge_empty),
         .dbg_cam_bridge_full    (cam_bridge_full),
         .dbg_ddr_init_done      (ddr_init_done),
         .dbg_ddr_write_active   (ddr_write_active),
         .dbg_frame_ready        (frame_ready),
         .dbg_ddr_read_valid     (ddr_read_valid),
         .dbg_rd_fifo_wr_en      (rd_fifo_wr_en)
    );

endmodule
