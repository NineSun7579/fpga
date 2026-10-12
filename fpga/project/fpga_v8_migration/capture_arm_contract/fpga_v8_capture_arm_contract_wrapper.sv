`timescale 1ns/1ps
// Isolated integration candidate.  Existing endpoint, lease, camera and DMA
// implementations are bound by source path in bindings_manifest.json; this
// wrapper owns only the new ARM transaction boundary.
module fpga_v8_capture_arm_contract_wrapper #(
    parameter DATA_WIDTH=16, parameter AXI_DATA_WIDTH=128,
    parameter CAM_DATA_LEN=38400,
    parameter [31:0] BANK0_ADDR=32'h01800000,
    parameter [31:0] BANK1_ADDR=32'h01a00000
) (
    input wire clk, input wire rst_n,
    input wire [31:0] s_axil_awaddr, input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid, output wire s_axil_awready,
    input wire [31:0] s_axil_wdata, input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid, output wire s_axil_wready,
    output wire [1:0] s_axil_bresp, output wire s_axil_bvalid,
    input wire s_axil_bready,
    input wire [31:0] s_axil_araddr, input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid, output wire s_axil_arready,
    output wire [31:0] s_axil_rdata, output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid, input wire s_axil_rready,
    input wire axi_cam_en, input wire [DATA_WIDTH-1:0] s_data,
    input wire s_data_valid, input wire s_hsync, input wire s_vsync,
    input wire dma_abort, output wire dma_abort_req, input wire dma_done,
    output wire [AXI_DATA_WIDTH-1:0] axi_data, output wire axi_data_valid,
    output wire axi_data_last, input wire axi_data_ready,
    output wire [31:0] axi_cmd_addr, output wire [31:0] axi_cmd_len,
    output wire axi_cmd_valid, input wire axi_cmd_ready,
    output wire [1:0] xdma_req, input wire [1:0] xdma_ack,
    output wire admitted_sof, output wire capture_bank, output wire publish,
    output wire [31:0] publish_seq, output wire retired_error,
    output wire engine_idle, output wire [1:0] bank0_state, output wire [1:0] bank1_state,
    output wire armed, output wire config_ok, output wire protocol_fault,
    output wire lease_block, output wire [31:0] published_count,
    output wire [31:0] failed_count, output wire [31:0] rejected_release_count,
    output wire arm_busy_reject,
    output wire input_valid, input wire input_ready, output wire input_raw_valid,
    output wire [31:0] input_src_addr,input_length,input_seq,input_generation,
    output wire [2:0] input_camera, output wire input_bank, output wire [63:0] input_token,
    input wire release_valid, output wire release_ready,
    input wire [2:0] release_camera, input wire release_bank,
    input wire [31:0] release_seq,release_generation, input wire [63:0] release_token,
    output wire release_accept,release_reject,
    output wire [15:0] axi_data_available,
    output wire capture_flush_o,frame_good_o,capture_overflow_o,
    output wire [31:0] dbg_fault_snapshot,dbg_reject_counts,dbg_input_pixels,
    output wire [31:0] dbg_axi_cnt,dbg_axi_num,dbg_zdin,dbg_zout,dbg_state,dbg_last_cnt,dbg_wd_cnt
);
    wire cfgv, cfg_stage_ready, cfg_stage_v, manager_config_ready;
    wire [31:0] cfggen, cfg_stage_gen;
    wire cfga, cfge, staged_accept, staged_reject;
    wire epoch_start;
    wire host_valid, host_ready, host_release_valid, host_release_ready;
    wire [31:0] host_src_addr,host_length,host_seq,host_generation;
    wire [2:0] host_camera,host_release_camera;
    wire [31:0] host_release_seq,host_release_generation;
    wire host_bank,host_release_bank;
    wire [63:0] host_token,host_release_token;
    wire host_release_accept,host_release_reject;
    wire [31:0] accepted_generation,accepted_configs,accepted_releases,accepted_claims;
    wire [31:0] rejected_claims,bad_acks,rejected_configs;
    wire manager_lease_block;
    // The raw commit has priority on its sampling edge.  It is independent
    // of manager READY; the registered stage then continues the exclusion.
    assign lease_block = manager_lease_block | cfgv;

    fpga_v8_capture_control_axil_arm_v2 capture_control (
        .clk(clk),.rst_n(rst_n),
        .config_valid(cfgv),.config_ready(manager_config_ready),.config_generation(cfggen),
        .config_accept(cfga),.config_reject(cfge),
        .epoch_start(epoch_start),.armed(armed),.config_ok(config_ok),
        .protocol_fault(protocol_fault),.bank0_state(bank0_state),.bank1_state(bank1_state),
        .host_valid(host_valid),.host_ready(host_ready),.host_src_addr(host_src_addr),
        .host_length(host_length),.host_seq(host_seq),.host_generation(host_generation),
        .host_camera(host_camera),.host_bank(host_bank),.host_token(host_token),
        .host_release_valid(host_release_valid),.host_release_ready(host_release_ready),
        .host_release_camera(host_release_camera),.host_release_bank(host_release_bank),
        .host_release_seq(host_release_seq),.host_release_generation(host_release_generation),
        .host_release_token(host_release_token),.host_release_accept(host_release_accept),
        .host_release_reject(host_release_reject),.published_count(published_count),
        .failed_count(failed_count),.rejected_release_count(rejected_release_count),
        .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),
        .s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
        .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),
        .s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
        .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
        .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),
        .s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
        .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),
        .s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready)
    );

    assign arm_busy_reject = cfgv && !manager_config_ready;

    fpga_v8_capture_lease manager (
        .clk(clk),.rst(!rst_n),.config_valid(cfgv),.config_ready(manager_config_ready),
        .config_generation(cfggen),.config_accept(cfga),.config_reject(cfge),
        .epoch_start(epoch_start),.armed(armed),.config_ok(config_ok),.engine_idle(engine_idle),
        .capture_bank(capture_bank),.admitted_sof(admitted_sof),.publish(publish),
        .publish_seq(publish_seq),.retired_error(retired_error),.lease_block(manager_lease_block),
        .bank0_state(bank0_state),.bank1_state(bank1_state),.protocol_fault(protocol_fault),
        .input_valid(input_valid),.input_ready(input_ready),.input_raw_valid(input_raw_valid),
        .input_src_addr(input_src_addr),.input_length(input_length),.input_seq(input_seq),
        .input_generation(input_generation),.input_camera(input_camera),.input_bank(input_bank),
        .input_token(input_token),.release_valid(release_valid),.release_ready(release_ready),
        .release_camera(release_camera),.release_bank(release_bank),.release_seq(release_seq),
        .release_generation(release_generation),.release_token(release_token),
        .release_accept(release_accept),.release_reject(release_reject),.host_valid(host_valid),.host_ready(host_ready),
        .host_src_addr(host_src_addr),.host_length(host_length),.host_seq(host_seq),
        .host_generation(host_generation),.host_camera(host_camera),.host_bank(host_bank),
        .host_token(host_token),.host_release_valid(host_release_valid),.host_release_ready(host_release_ready),
        .host_release_camera(host_release_camera),.host_release_bank(host_release_bank),
        .host_release_seq(host_release_seq),.host_release_generation(host_release_generation),
        .host_release_token(host_release_token),.host_release_accept(host_release_accept),
        .host_release_reject(host_release_reject),.published_count(published_count),
        .failed_count(failed_count),.rejected_release_count(rejected_release_count)
    );

    fpga_v8_capture_ov5640_ddr #(.DATA_WIDTH(DATA_WIDTH),.AXI_DATA_WIDTH(AXI_DATA_WIDTH),
        .CAM_DATA_LEN(CAM_DATA_LEN),.BANK0_ADDR(BANK0_ADDR),.BANK1_ADDR(BANK1_ADDR)) capture (
        .axi_clk(clk),.axi_rst(!rst_n),.epoch_start(epoch_start),.lease_block(lease_block),
        .dma_abort(dma_abort),.dma_abort_req(dma_abort_req),.dma_done(dma_done),.axi_data_available(axi_data_available),
        .axi_cam_en(axi_cam_en),.s_data(s_data),.s_data_valid(s_data_valid),.s_hsync(s_hsync),.s_vsync(s_vsync),
        .axi_data(axi_data),.axi_data_valid(axi_data_valid),.axi_data_last(axi_data_last),.axi_data_ready(axi_data_ready),
        .axi_cmd_addr(axi_cmd_addr),.axi_cmd_len(axi_cmd_len),.axi_cmd_valid(axi_cmd_valid),.axi_cmd_ready(axi_cmd_ready),
        .xdma_req(xdma_req),.xdma_ack(xdma_ack),.admitted_sof(admitted_sof),.capture_bank(capture_bank),
        .publish(publish),.publish_seq(publish_seq),.retired_error(retired_error),.engine_idle(engine_idle),
        .capture_flush_o(capture_flush_o),.frame_good_o(frame_good_o),.capture_overflow_o(capture_overflow_o),
        .dbg_fault_snapshot(dbg_fault_snapshot),.dbg_reject_counts(dbg_reject_counts),
        .dbg_input_pixels(dbg_input_pixels),.dbg_axi_cnt(dbg_axi_cnt),.dbg_axi_num(dbg_axi_num),
        .dbg_zdin(dbg_zdin),.dbg_zout(dbg_zout),.dbg_state(dbg_state),.dbg_last_cnt(dbg_last_cnt),.dbg_wd_cnt(dbg_wd_cnt)
    );
endmodule
