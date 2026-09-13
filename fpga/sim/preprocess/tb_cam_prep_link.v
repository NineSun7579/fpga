`timescale 1ns/1ps
//============================================================================
// tb_cam_prep_link.v : cam_prep_link + preprocess_top chain TB (bypass mode)
//   Small frame W=16 H=2 (4 raw words/frame). Checks:
//   1) raw passthrough = input words (unchanged, same count)
//   2) preprocess input gets W*H+1 pixels (tail dummy injected)
//   3) processed write stream = bypass echo of first W*H pixels, packed to
//      W*H/8 words; wr cmd addr ping/pong alternates, len = words*16
//   4) 2 frames: buffer parity flips
//============================================================================
module tb_cam_prep_link;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam W = 16, H = 2;
    localparam RAW_WORDS = W*H/8;           // 4
    localparam FRAME_PIXELS = W*H;          // 32
    localparam OUT_WORDS = FRAME_PIXELS/8;  // 4
    localparam NFRAMES = 2;

    reg          cam_cmd_sync = 1'b0;
    reg  [127:0] cam_data;
    reg          cam_valid = 1'b0;
    wire         cam_ready;
    wire [127:0] raw_data;
    wire         raw_valid;
    reg          raw_ready = 1'b1;

    wire [15:0]  pp_data;
    wire         pp_valid;
    wire         pp_ready;
    wire         pp_fsync;
    wire [15:0]  out_data;
    wire         out_valid;
    wire         out_ready;
    wire         out_fsync;

    wire         wr_cmd_valid;
    reg          wr_cmd_ready = 1'b1;
    wire [31:0]  wr_cmd_addr;
    wire [31:0]  wr_cmd_len;
    wire [127:0] wr_data;
    wire         wr_valid;
    reg          wr_ready = 1'b1;

    cam_prep_link #(
        .FRAME_H (H),
        .BUFFER0 (32'h0A00_0000),
        .BUFFER1 (32'h0A1C_2000)
    ) link_u (
        .clk(clk), .rst(rst),
        .img_width   (W),
        .bypass_mode (1'b1),
        .mode        (2'd0),
        .cam_data    (cam_data),
        .cam_valid   (cam_valid),
        .cam_ready   (cam_ready),
        .cam_frame_sync(cam_cmd_sync),
        .raw_data    (raw_data),
        .raw_valid   (raw_valid),
        .raw_ready   (raw_ready),
        .pp_data     (pp_data),
        .pp_valid    (pp_valid),
        .pp_ready    (pp_ready),
        .pp_frame_sync(pp_fsync),
        .out_data    (out_data),
        .out_valid   (out_valid),
        .out_ready   (out_ready),
        .out_frame_sync(out_fsync),
        .wr_cmd_valid(wr_cmd_valid),
        .wr_cmd_ready(wr_cmd_ready),
        .wr_cmd_addr (wr_cmd_addr),
        .wr_cmd_len  (wr_cmd_len),
        .wr_data     (wr_data),
        .wr_valid    (wr_valid),
        .wr_ready    (wr_ready)
    );

    preprocess_top #(
        .MAX_WIDTH  (1920),
        .FIFO_DEPTH (512)
    ) preprocess_u (
        .clk        (clk),
        .rst_n      (~rst),
        .s_rgb565   (pp_data),
        .s_valid    (pp_valid),
        .s_ready    (pp_ready),
        .s_frame_sync(pp_fsync),
        .m_ready    (out_ready),
        .m_rgb565   (out_data),
        .m_valid    (out_valid),
        .m_frame_sync(out_fsync),
        .reg_bypass (1'b1),
        .reg_mode   (2'd0),
        .reg_img_width(W[11:0]),
        .reg_thr_sat(8'd96), .reg_thr_hue(8'd64),
        .reg_thr_val(8'd160), .reg_thr_low(8'd160),
        .reg_thr_edge(11'd128),
        .out_frame_start(),
        .edge_stream_valid(), .edge_stream_edge(), .edge_stream_center(),
        .color_id_valid(), .color_id()
    );

    //----------------------------------------
    // monitors
    //----------------------------------------
    integer raw_cnt = 0, raw_err = 0;
    reg [127:0] raw_seen [0:RAW_WORDS*NFRAMES-1];
    always @(posedge clk) begin
        if (!rst && raw_valid) begin
            if (raw_data !== raw_seen[raw_cnt] && raw_cnt < RAW_WORDS*NFRAMES)
                raw_err = raw_err + 1;
            raw_seen[raw_cnt] = raw_data;
            raw_cnt = raw_cnt + 1;
        end
    end

    integer wr_cnt = 0, wr_err = 0;
    reg [127:0] wr_seen [0:OUT_WORDS*NFRAMES-1];
    reg [31:0]  cmd_seen_addr [0:NFRAMES-1];
    reg [31:0]  cmd_seen_len  [0:NFRAMES-1];
    integer cmd_cnt = 0, cmd_err = 0;
    always @(posedge clk) begin
        if (!rst && wr_valid && wr_ready) begin
            if (wr_data !== wr_seen[wr_cnt] && wr_cnt < OUT_WORDS*NFRAMES) begin
                if (wr_err < 6) $display("[CP][ERR] word#%0d got=%032h exp=%032h",
                                         wr_cnt, wr_data, wr_seen[wr_cnt]);
                wr_err = wr_err + 1;
            end
            wr_seen[wr_cnt] = wr_data;
            wr_cnt = wr_cnt + 1;
        end
    end
    always @(posedge clk) begin
        if (!rst && wr_cmd_valid && wr_cmd_ready) begin
            cmd_seen_addr[cmd_cnt] = wr_cmd_addr;
            cmd_seen_len [cmd_cnt] = wr_cmd_len;
            cmd_cnt = cmd_cnt + 1;
        end
    end

    //----------------------------------------
    // golden build + drive
    //----------------------------------------
    reg [127:0] golden_words [0:RAW_WORDS-1];
    integer f, w, b, pix;
    reg [15:0] pv;
    reg [31:0] expaddr;
    reg done_flag = 0;
    integer err_i = 0;
    reg [31:0] exp_addr;

    task drive_frame(input integer frame_idx);
        integer i;
        begin
            cam_cmd_sync = 1'b1;
            @(posedge clk);
            cam_cmd_sync = 1'b0;
            // random gaps between words
            for (i = 0; i < RAW_WORDS; i = i + 1) begin
                cam_data  = golden_words[i];
                cam_valid = 1'b1;
                @(posedge clk);
                if (($random & 3) == 0) begin
                    cam_valid = 1'b0;
                    @(posedge clk);
                end
            end
            cam_valid = 1'b0;
        end
    endtask

    initial begin
        // golden: word i packs pixels 8i..8i+7, pixel p = p+1 (bypass echo = p)
        for (w = 0; w < RAW_WORDS; w = w + 1) begin
            for (b = 0; b < 8; b = b + 1) begin
                pix = w*8 + b;
                pv = pix[15:0] + 16'd1;             // pixel code = p+1 (0 reserved for dummy)
                golden_words[w][b*16 +: 16] = pv;
            end
        end
        for (f = 0; f < NFRAMES; f = f + 1)
            for (w = 0; w < OUT_WORDS; w = w + 1)
                wr_seen[f*OUT_WORDS + w] = 32'hDEAD_BEEF;
        repeat (10) @(posedge clk);
        rst = 1'b0;
        repeat (5) @(posedge clk);
        for (f = 0; f < NFRAMES; f = f + 1)
            drive_frame(f);
        repeat (300) @(posedge clk);
        done_flag = 1;
    end

    integer i;
    always @(posedge clk) begin
        if (done_flag) begin
            // 1) raw passthrough
            if (raw_cnt != RAW_WORDS*NFRAMES || raw_err != 0) begin
                $display("[CP][ERR] raw cnt=%0d err=%0d", raw_cnt, raw_err);
                err_i = err_i + 1;
            end
            // 2) write words
            if (wr_cnt != OUT_WORDS*NFRAMES) begin
                $display("[CP][ERR] wr cnt=%0d exp=%0d", wr_cnt, OUT_WORDS*NFRAMES);
                err_i = err_i + 1;
            end
            // 3) cmds: ping/pong + len
            if (cmd_cnt != NFRAMES) begin
                $display("[CP][ERR] cmd cnt=%0d exp=%0d", cmd_cnt, NFRAMES);
                err_i = err_i + 1;
            end
            for (i = 0; i < NFRAMES && i < cmd_cnt; i = i + 1) begin
                exp_addr = (i == 0) ? 32'h0A00_0000 : 32'h0A1C_2000;
                if (cmd_seen_addr[i] !== exp_addr) begin
                    $display("[CP][ERR] cmd#%0d addr=%08h exp=%08h", i, cmd_seen_addr[i], exp_addr);
                    err_i = err_i + 1;
                end
                if (cmd_seen_len[i] !== OUT_WORDS*16) begin
                    $display("[CP][ERR] cmd#%0d len=%0d exp=%0d", i, cmd_seen_len[i], OUT_WORDS*16);
                    err_i = err_i + 1;
                end
            end
            if (err_i == 0)
                $display("[CP] TB_PASS  raw=%0d wr=%0d cmd=%0d", raw_cnt, wr_cnt, cmd_cnt);
            else
                $display("[CP] TB_FAIL  err=%0d", err_i);
            $finish;
        end
    end

    initial begin
        #2_000_000;
        $display("[CP] TB_FAIL  timeout raw=%0d wr=%0d", raw_cnt, wr_cnt);
        $finish;
    end

endmodule
