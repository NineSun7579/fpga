`timescale 1ns/1ps
module tb_sfp_diag;
    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;
    reg awvalid = 0, wvalid = 0, arvalid = 0;
    reg bready = 0, rready = 0;
    reg [31:0] awaddr = 0, wdata = 0, araddr = 0;
    reg [3:0] wstrb = 15, buttons = 0;
    reg capture = 0;
    wire [1:0] awready, wready, bvalid, arready, rvalid;
    wire [31:0] rdata [0:1];
    wire [1:0] bresp [0:1], rresp [0:1];
    wire [3:0] led [0:1], sticky [0:1];
    wire [31:0] ts0 [0:1];
    integer checks = 0;
    reg [31:0] captured;

    // Both instances receive identical transactions. Instance 0 deliberately
    // omits SFP_DIAG_EN, testing the public default with live diagnostic inputs.
`define PORTS(N) \
        .clk(clk), .rst_n(rst_n), \
        .s_axi_awvalid(awvalid), .s_axi_awready(awready[N]), .s_axi_awaddr(awaddr), \
        .s_axi_wvalid(wvalid), .s_axi_wready(wready[N]), .s_axi_wdata(wdata), \
        .s_axi_wstrb(wstrb), .s_axi_bvalid(bvalid[N]), .s_axi_bready(bready), .s_axi_bresp(bresp[N]), \
        .s_axi_arvalid(arvalid), .s_axi_arready(arready[N]), .s_axi_araddr(araddr), \
        .s_axi_rvalid(rvalid[N]), .s_axi_rready(rready), .s_axi_rdata(rdata[N]), .s_axi_rresp(rresp[N]), \
        .inj_busy(1'b1), .inj_done(1'b1), .inj_done_fid(16'h1234), \
        .pipe_frame_sync(1'b1), .pipe_fifo_afull(1'b0), .npu_busy(1'b1), .out_frame_cnt(8'h56), \
        .btn_toggle_evt(buttons), .btn_level_sync(4'h9), .btn_sticky(sticky[N]), .led_ctrl(led[N]), \
        .lane_left_type(2'd1), .lane_right_type(2'd2), \
        .lane_left_valid(1'b1), .lane_right_valid(1'b0), .lane_frame_upd(1'b1), \
        .ts_cap_pulse(capture), .ts_prep_pulse(1'b0), .ts_npu_pulse(1'b0), .ts_dma_pulse(1'b0), \
        .ts_value0(ts0[N]), .ts_value1(), .ts_value2(), .ts_value3(), \
        .prep_bypass(), .prep_mode(), .prep_img_width(), \
        .prep_thr_sat(), .prep_thr_hue(), .prep_thr_val(), .prep_thr_low(), .prep_thr_edge(), \
        .prep_lane_roi_top(), .prep_lane_roi_bot(), .prep_lane_row_thr(), .prep_lane_dash_thr(), \
        .inj_addr(), .inj_len(), .inj_frame_id(), .inj_start(), .inj_done_clr(), .btn_sticky_clr(), \
        .dbg_pp_beats(32'h87654321), .dbg_prep_aw(32'h11223344), \
        .dbg_prep_w(32'h55667788), .dbg_prep_b(32'h99aabbcc), \
        .sfp_diag_status(32'ha1200001), .sfp_diag_fault5(32'hb1300002), \
        .sfp_diag_fault6(32'hc1400003), .sfp_diag_pixels5(32'hd1500004), \
        .sfp_diag_pixels6(32'he1600005), .sfp_diag_states(32'hf1700006), \
        .sfp_diag_rejects(32'h91800007)
    prep_regs #(.TICK_DIV(4)) legacy (`PORTS(0));
    prep_regs #(.TICK_DIV(4), .SFP_DIAG_EN(1)) diag (`PORTS(1));
`undef PORTS

    task read_check(input [31:0] addr, input [31:0] old_value, input [31:0] diag_value);
        begin
            @(negedge clk); araddr = addr; arvalid = 1;
            @(posedge clk);
            while (arready !== 2'b11) @(posedge clk);
            @(negedge clk); arvalid = 0;
            while (rvalid !== 2'b11) @(negedge clk);
            if (rdata[0] !== old_value || rdata[1] !== diag_value ||
                rresp[0] !== 0 || rresp[1] !== 0)
                $fatal(1, "READ %h legacy=%h expected=%h diag=%h expected=%h",
                       addr, rdata[0], old_value, rdata[1], diag_value);
            // Hold the response for two cycles to exercise backpressure.
            repeat (2) begin
                @(negedge clk);
                if (rvalid !== 2'b11 || rdata[0] !== old_value || rdata[1] !== diag_value)
                    $fatal(1, "Unstable read response");
            end
            rready = 1;
            @(negedge clk); rready = 0;
            checks = checks + 1;
        end
    endtask

    task write_reg(input [31:0] addr, input [31:0] value, input [3:0] strobes);
        begin
            // AW precedes W, so the test also covers independent channel capture.
            @(negedge clk); awaddr = addr; awvalid = 1;
            @(posedge clk);
            while (awready !== 2'b11) @(posedge clk);
            @(negedge clk); awvalid = 0;
            repeat (2) @(negedge clk);
            wdata = value; wstrb = strobes; wvalid = 1;
            @(posedge clk);
            while (wready !== 2'b11) @(posedge clk);
            @(negedge clk); wvalid = 0;
            while (bvalid !== 2'b11) @(negedge clk);
            if (bresp[0] !== 0 || bresp[1] !== 0) $fatal(1, "Write response error");
            bready = 1;
            @(negedge clk); bready = 0;
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst_n = 1;
        repeat (6) @(negedge clk);
        buttons = 4'ha; capture = 1;
        @(negedge clk); buttons = 0; capture = 0;
        captured = ts0[0];
        if (captured == 0 || ts0[1] !== captured) $fatal(1, "Timestamp capture failed");
        read_check(32'h20000120, 32'h12340003, 32'ha1200001);
        // Preserve the existing PIPE_STATUS concatenation exactly (frame count at [15:8]).
        read_check(32'h20000130, 32'h00005605, 32'hb1300002);
        read_check(32'h20000140, 32'ha, 32'hc1400003);
        read_check(32'h20000150, 32'h0, 32'hd1500004);
        read_check(32'h20000160, 32'h189, 32'he1600005);
        read_check(32'h20000170, captured, 32'hf1700006);
        read_check(32'h20000180, 32'h87654321, 32'h91800007);

        // Diagnostic reads must not replace LED writes, button W1C, or TS clear.
        write_reg(32'h20000150, 32'hb, 4'hf);
        if (led[0] !== 4'hb || led[1] !== 4'hb) $fatal(1, "LED write changed");
        read_check(32'h20000150, 32'hb, 32'hd1500004);
        write_reg(32'h20000144, 32'h2, 4'hf);
        if (sticky[0] !== 4'h8 || sticky[1] !== 4'h8) $fatal(1, "Button W1C changed");
        read_check(32'h20000140, 32'h8, 32'hc1400003);
        read_check(32'h20000144, 32'h9, 32'h9);
        write_reg(32'h2000017c, 0, 4'hf);
        read_check(32'h20000170, 0, 32'hf1700006);
        read_check(32'h20000174, 0, 0);
        read_check(32'h20000178, 0, 0);
        read_check(32'h2000017c, 0, 0);
        read_check(32'h20000184, 32'h11223344, 32'h11223344);
        read_check(32'h20000188, 32'h55667788, 32'h55667788);
        read_check(32'h2000018c, 32'h99aabbcc, 32'h99aabbcc);
        write_reg(32'h20000104, 32'h11223344, 4'h5);
        read_check(32'h20000104, 32'ha0226044, 32'ha0226044);
        write_reg(32'h20000110, 32'h06001234, 4'hf);
        read_check(32'h20000110, 32'h06001234, 32'h06001234);
        // Read-only and unmapped writes remain harmless.
        write_reg(32'h20000120, 32'hffffffff, 4'hf);
        read_check(32'h20000120, 32'h12340003, 32'ha1200001);
        read_check(32'h200001f0, 0, 0);
        $display("SFP_DIAG_PASS: %0d paired reads, default/enabled mapping and original writes", checks);
        $finish;
    end
    initial begin
        #100000;
        $fatal(1, "AXI-Lite test timeout");
    end
endmodule
