// tb_ov5640_ddr_w_tag.v -- [FRTAG 2026-09-14] standalone testbench for the modified
// ov5640_ddr_w_ctrl (frame-tag FSM). Reproduces the wrapper mux topology of
// ov5640_ddr.v: camera stream + tag substitution, feeding a simplified
// length-driven axi_dma_write model (accepts back-to-back commands).
//
// Checks per frame f (1-based):
//   1. cmd1 = {frame_base, CAM_DATA_LEN*16} with ping-pong base alternation
//   2. cmd2 = {frame_base + FRAME_BYTES, 16}  (the tag command)
//   3. tag beat carries the 32-bit frame counter == f, exactly one beat
//   4. xdma_req bits accumulate (never acked here)
`timescale 1ns/1ps

module tb_ov5640_ddr_w_tag;

    localparam AW = 32, LW = 32, DW = 128;
    localparam CAM_DATA_LEN = 8;                 // 8 beats (16B each) per "frame"
    localparam FRAME_BYTES  = CAM_DATA_LEN * 16; // 128
    localparam NFRAMES      = 4;

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg  rst = 1'b1;
    reg  s_vsync = 1'b0;

    reg  [AW-1:0] addr1 = 32'h00800000;
    reg  [AW-1:0] addr2 = 32'h00A00000;
    reg  [$clog2(CAM_DATA_LEN):0] data_len = CAM_DATA_LEN;

    // ---------------- camera stream (behaves like ov5640_ddr_w output) ----------
    reg  [DW-1:0] cam_data  = {DW{1'b0}};
    reg           cam_valid = 1'b0;
    integer       cam_beat  = 0;

    // ---------------- ctrl + wrapper mux ----------------------------------------
    wire [AW-1:0] cmd_addr;
    wire [LW-1:0] cmd_len;
    wire          cmd_valid;
    reg           cmd_ready = 1'b0;
    wire          tag_active;
    wire [DW-1:0] tag_data;
    wire          tag_ready;

    wire [DW-1:0] m_data  = tag_active ? tag_data : cam_data;
    wire          m_valid = tag_active ? 1'b1    : cam_valid;
    wire          m_ready;
    wire          cam_ready = m_ready & ~tag_active;
    wire          cam_last  = cam_valid & cam_ready & (cam_beat == CAM_DATA_LEN-1);

    wire [1:0] xdma_req;
    wire [1:0] xdma_ack = 2'b00;    // never ack: req bits just accumulate

    ov5640_ddr_w_ctrl #(
        .AXI_ADDR_WIDTH(AW),
        .AXI_LEN_WIDTH (LW),
        .AXI_DATA_WIDTH(DW),
        .CAM_DATA_LEN  (CAM_DATA_LEN)
    ) dut (
        .axi_clk        (clk        ),
        .axi_rst        (rst        ),
        .cam_data_addr_1(addr1      ),
        .cam_data_addr_2(addr2      ),
        .cam_data_len   (data_len   ),
        .s_vsync        (s_vsync    ),
        .axi_data_valid (cam_valid  ),
        .axi_data_last  (cam_last   ),
        .axi_data_ready (cam_ready  ),
        .axi_cmd_addr   (cmd_addr   ),
        .axi_cmd_len    (cmd_len    ),
        .axi_cmd_valid  (cmd_valid  ),
        .axi_cmd_ready  (cmd_ready  ),
        .tag_active     (tag_active ),
        .tag_data       (tag_data   ),
        .tag_ready      (tag_ready  ),
        .xdma_req       (xdma_req   ),
        .xdma_ack       (xdma_ack   )
    );

    // ---------------- simplified length-driven write engine ---------------------
    // trans=0: cmd_ready=1. On accept: latch addr/len, consume len>>4 beats
    // (back-to-back, like act_burst_len gating), then a short B delay.
    reg          trans   = 1'b0;
    reg  [31:0]  e_addr  = 32'd0;
    integer      e_beats = 0;
    reg  [2:0]   b_cnt   = 3'd0;

    reg [AW-1:0] log_addr [0:63];
    reg [LW-1:0] log_len  [0:63];
    reg [DW-1:0] beat_data[0:255];
    integer      n_cmds  = 0;
    integer      n_beats = 0;

    always @(posedge clk) begin
        if (rst) begin
            trans <= 1'b0; cmd_ready <= 1'b0; b_cnt <= 3'd0;
        end
        else begin
            if (!trans) begin
                if (b_cnt != 3'd0) begin
                    b_cnt <= b_cnt - 3'd1;              // B-response latency
                end
                else if (cmd_ready && cmd_valid) begin
                    e_addr  <= cmd_addr;
                    e_beats <= cmd_len >> 4;
                    trans   <= 1'b1;
                    cmd_ready <= 1'b0;
                    log_addr[n_cmds] <= cmd_addr;
                    log_len [n_cmds] <= cmd_len;
                    n_cmds <= n_cmds + 1;
                end
                else begin
                    cmd_ready <= 1'b1;
                end
            end
            else begin
                if (m_valid && m_ready) begin
                    beat_data[n_beats] <= m_data;
                    n_beats <= n_beats + 1;
                    e_beats <= e_beats - 1;
                    if (e_beats == 1) begin
                        trans <= 1'b0;
                        b_cnt <= 3'd3;                  // engine busy for 3 cycles
                    end
                end
            end
        end
    end

    // beat consumption gate: engine only accepts beats while a command is active
    assign m_ready   = trans && (e_beats > 0);
    assign tag_ready = m_ready;

    // ---------------- helpers ---------------------------------------------------
    integer errors = 0;
    task check(input integer cond, input [255:0] msg);
        if (!cond) begin
            errors = errors + 1;
            $display("[FAIL] %0s  (t=%0t)", msg, $time);
        end
    endtask

    // drive one camera frame: 1-cycle vsync pulse, then CAM_DATA_LEN beats.
    // Beats only start once the engine accepted the frame command, and are
    // consumed back-to-back (m_ready stays high for the whole command).
    task send_frame(input [31:0] seed);
        integer i;
        begin
            @(negedge clk);
            s_vsync = 1'b1; @(negedge clk); s_vsync = 1'b0;
            wait (trans === 1'b1 && e_beats == CAM_DATA_LEN);  // cmd1 accepted
            @(negedge clk);
            for (i = 0; i < CAM_DATA_LEN; i = i + 1) begin
                cam_valid <= 1'b1;
                cam_data  <= {seed + i[31:0], 24'hC0DE, i[15:0]};
                cam_beat  = i;
                @(negedge clk);
            end
            cam_valid <= 1'b0;
            cam_beat  = 0;
        end
    endtask

    // ---------------- main sequence ---------------------------------------------
    integer f, idx;
    reg [AW-1:0] exp_base;
    initial begin
        rst = 1'b1; cam_beat = 0;
        repeat (10) @(negedge clk);
        rst = 1'b0;
        repeat (5) @(negedge clk);

        for (f = 1; f <= NFRAMES; f = f + 1) begin
            exp_base = (f % 2 == 1) ? addr1 : addr2;
            send_frame(f * 16);

            idx = (f - 1) * 2;
            wait (n_cmds >= idx + 2);            // both commands logged
            wait (n_beats >= f * (CAM_DATA_LEN + 1));  // tag beat consumed
            @(negedge clk);

            check(log_addr[idx]   === exp_base,               "cmd1 addr");
            check(log_len [idx]   === CAM_DATA_LEN * 16,      "cmd1 len");
            check(log_addr[idx+1] === exp_base + FRAME_BYTES, "cmd2 (tag) addr");
            check(log_len [idx+1] === 32'd16,                 "cmd2 (tag) len");
            check(beat_data[n_beats-1][31:0] === f[31:0],     "tag beat = frame_cnt");
        end

        check(xdma_req === 2'b11, "xdma_req both bits set");

        if (errors == 0)
            $display("=== TB PASS: %0d frames, %0d commands, %0d beats ===", NFRAMES, n_cmds, n_beats);
        else
            $display("=== TB FAIL: %0d errors ===", errors);
        $finish;
    end

    // global timeout
    initial begin
        #2000000;
        $display("[FAIL] global timeout, n_cmds=%0d n_beats=%0d", n_cmds, n_beats);
        $finish;
    end
endmodule
