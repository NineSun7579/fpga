`timescale 1ns/1ps
module tb_fpga_v8_coop_control_axil #(
    parameter [31:0] OUTPUT_BANK0_ADDR = 32'h08000000,
    parameter [31:0] OUTPUT_BANK1_ADDR = 32'h08200000,
    parameter [31:0] OUTPUT_LENGTH = 32'd1228800
);
    reg core_clk = 0;
    always #5 core_clk = !core_clk;
    reg rst_n = 0;
    reg input_valid, input_raw_valid;
    wire input_ready, input_claim, input_reject;
    reg [31:0] input_src_addr, input_source_seq, input_generation;
    reg [2:0] input_camera;
    reg input_camera_bank;
    reg [63:0] input_lease_token;
    wire cmd_valid;
    reg cmd_ready;
    wire [31:0] cmd_src_addr, cmd_dst_addr, cmd_frame_id;
    reg bridge_busy, bridge_done, bridge_error, bridge_cmd_error;
    wire src_release_valid;
    reg src_release_ready;
    wire [31:0] src_release_addr, src_release_seq, src_release_generation;
    wire [2:0] src_release_camera;
    wire src_release_camera_bank;
    wire [63:0] src_release_token;
    wire busy;
    wire [1:0] bank0_state, bank1_state;
    reg [31:0] s_axil_awaddr, s_axil_wdata, s_axil_araddr;
    reg [2:0] s_axil_awprot = 0, s_axil_arprot = 0;
    reg s_axil_awvalid, s_axil_wvalid, s_axil_bready;
    reg s_axil_arvalid, s_axil_rready;
    reg [3:0] s_axil_wstrb;
    wire s_axil_awready, s_axil_wready, s_axil_bvalid;
    wire s_axil_arready, s_axil_rvalid;
    wire [1:0] s_axil_bresp, s_axil_rresp;
    wire [31:0] s_axil_rdata;
    fpga_v8_coop_control_axil #(
        .OUTPUT_BANK0_ADDR(OUTPUT_BANK0_ADDR),
        .OUTPUT_BANK1_ADDR(OUTPUT_BANK1_ADDR), .OUTPUT_LENGTH(OUTPUT_LENGTH)
    ) dut (
        .core_clk(core_clk), .rst_n(rst_n),
        .input_valid(input_valid), .input_ready(input_ready),
        .input_raw_valid(input_raw_valid), .input_src_addr(input_src_addr),
        .input_source_seq(input_source_seq), .input_generation(input_generation),
        .input_camera(input_camera), .input_camera_bank(input_camera_bank),
        .input_lease_token(input_lease_token), .input_claim(input_claim),
        .input_reject(input_reject), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_src_addr(cmd_src_addr), .cmd_dst_addr(cmd_dst_addr),
        .cmd_frame_id(cmd_frame_id), .bridge_busy(bridge_busy),
        .bridge_done(bridge_done), .bridge_error(bridge_error),
        .bridge_cmd_error(bridge_cmd_error), .src_release_valid(src_release_valid),
        .src_release_ready(src_release_ready), .src_release_addr(src_release_addr),
        .src_release_seq(src_release_seq), .src_release_generation(src_release_generation),
        .src_release_camera(src_release_camera), .src_release_camera_bank(src_release_camera_bank),
        .src_release_token(src_release_token), .busy(busy),
        .bank0_state(bank0_state), .bank1_state(bank1_state),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awprot(s_axil_awprot),
        .s_axil_awvalid(s_axil_awvalid), .s_axil_awready(s_axil_awready),
        .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb),
        .s_axil_wvalid(s_axil_wvalid), .s_axil_wready(s_axil_wready),
        .s_axil_bresp(s_axil_bresp), .s_axil_bvalid(s_axil_bvalid), .s_axil_bready(s_axil_bready),
        .s_axil_araddr(s_axil_araddr), .s_axil_arprot(s_axil_arprot),
        .s_axil_arvalid(s_axil_arvalid), .s_axil_arready(s_axil_arready),
        .s_axil_rdata(s_axil_rdata), .s_axil_rresp(s_axil_rresp),
        .s_axil_rvalid(s_axil_rvalid), .s_axil_rready(s_axil_rready)
    );
    // Width/layout is independently checked by run_tests.py.
    localparam IN_BITS = 278;
    localparam OUT_BITS = 311;
    reg [IN_BITS-1:0] stimulus;
    wire [OUT_BITS-1:0] observation = {
        input_ready, input_claim, input_reject,
        cmd_valid, cmd_src_addr, cmd_dst_addr, cmd_frame_id,
        src_release_valid, src_release_addr, src_release_seq, src_release_generation,
        src_release_camera, src_release_camera_bank, src_release_token,
        busy, bank0_state, bank1_state,
        s_axil_awready, s_axil_wready, s_axil_bvalid, s_axil_bresp,
        s_axil_arready, s_axil_rvalid, s_axil_rdata, s_axil_rresp
    };
    reg [2047:0] vectors_path, trace_path;
    integer vectors_fd, trace_fd, result, cycles;
    initial begin
        if (!$value$plusargs("VECTORS=%s", vectors_path) ||
            !$value$plusargs("TRACE=%s", trace_path)) begin
            $display("CONTROL_FAIL missing file arguments");
            $finish;
        end
        vectors_fd = $fopen(vectors_path, "r");
        trace_fd = $fopen(trace_path, "w");
        if (!vectors_fd || !trace_fd) begin
            $display("CONTROL_FAIL cannot open vectors/trace");
            $finish;
        end
        cycles = 0;
        result = $fscanf(vectors_fd, "%h\n", stimulus);
        while (result == 1) begin
            @(negedge core_clk);
            {rst_n, input_valid, input_raw_valid, input_src_addr, input_source_seq,
             input_generation, input_camera, input_camera_bank, input_lease_token,
             cmd_ready, bridge_busy, bridge_done, bridge_error, bridge_cmd_error,
             src_release_ready, s_axil_awaddr, s_axil_awvalid,
             s_axil_wdata, s_axil_wstrb, s_axil_wvalid, s_axil_bready,
             s_axil_araddr, s_axil_arvalid, s_axil_rready} = stimulus;
            @(posedge core_clk);
            $fdisplay(trace_fd, "%h", observation);
            cycles = cycles + 1;
            result = $fscanf(vectors_fd, "%h\n", stimulus);
        end
        $fclose(vectors_fd);
        $fclose(trace_fd);
        $display("CONTROL_TRACE_PASS cycles=%0d", cycles);
        $finish;
    end
endmodule
