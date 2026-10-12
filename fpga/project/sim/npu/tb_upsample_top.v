`timescale 1ns/1ps
//============================================================================
// tb_upsample_top.v : upsample_top module-level TB (需求(2), cmd tie-ready)
//   golden: golden/ups_{in,exp}.mem  nearest 2x: out[r][c]=in[r>>1][c>>1]
//   Fake DMA: answers each s_cmd (addr,len) by streaming len/16 words from
//   the golden frame (row-major), honoring s_ready / s_last handshake.
//   Dump  : golden/hw_out_upsample_top.mem
//============================================================================
module tb_upsample_top;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    localparam H = 6, W = 8;
    localparam ROWBYTES = W*16;
    localparam NIN  = H*W;          // 48
    localparam NOUT = 4*NIN;        // 192

    reg [127:0] inm  [0:NIN-1];
    reg [127:0] expm [0:NOUT-1];

    reg         start;
    reg  [31:0] in_col_channel_num, row_num, calculate_cin_num, s_addr;
    wire [127:0] s_data;
    wire         s_valid, s_last;
    wire         s_ready;
    wire [31:0]  s_cmd_addr, s_cmd_len;
    wire         s_cmd_valid;
    wire         s_cmd_ready;
    reg          m_req;
    wire [127:0] m_data;
    wire         m_valid, m_last;

    upsample_top dut (
        .clk(clk), .rst(rst), .start(start),
        .in_col_channel_num(in_col_channel_num),
        .row_num(row_num),
        .calculate_cin_num(calculate_cin_num),
        .s_addr(s_addr),
        .s_data(s_data), .s_valid(s_valid), .s_last(s_last), .s_ready(s_ready),
        .s_cmd_addr(s_cmd_addr), .s_cmd_len(s_cmd_len),
        .s_cmd_valid(s_cmd_valid), .s_cmd_ready(s_cmd_ready),
        .m_data(m_data), .m_valid(m_valid), .m_last(m_last),
        .m_req(m_req)
    );

    //---------------- fake DMA ----------------
    reg         dma_vld = 0;
    reg [127:0] dma_dat = 0;
    reg [31:0]  dma_widx = 0, dma_left = 0;
    assign s_data  = dma_dat;
    assign s_valid = dma_vld;
    wire dma_last_w = (dma_left == 16);
    assign s_last  = dma_vld && dma_last_w;
    assign s_cmd_ready = !dma_vld;

    always @(posedge clk) begin
        if (rst) begin
            dma_vld <= 0; dma_widx <= 0; dma_left <= 0; dma_dat <= 0;
        end
        else if (!dma_vld) begin
            if (s_cmd_valid && s_cmd_ready) begin
                dma_widx <= (s_cmd_addr - s_addr) >> 4;
                dma_left <= s_cmd_len;
                dma_dat  <= inm[(s_cmd_addr - s_addr) >> 4];
                dma_vld  <= 1;
            end
        end
        else if (s_ready) begin
            if (dma_last_w) begin
                dma_vld <= 0;
            end
            else begin
                dma_widx <= dma_widx + 1;
                dma_left <= dma_left - 16;
                dma_dat  <= inm[dma_widx + 1];
            end
        end
    end

    //---------------- collect + judge ----------------
    integer ocnt = 0, err = 0, i;
    reg [127:0] outm [0:NOUT-1];

    always @(posedge clk) begin
        if (!rst && m_valid) begin
            outm[ocnt] <= m_data;
            ocnt = ocnt + 1;
        end
    end

    initial begin
        $readmemh("golden/ups_in.mem", inm);
        $readmemh("golden/ups_exp.mem", expm);
        start = 0; m_req = 1;
        in_col_channel_num = ROWBYTES; row_num = H; calculate_cin_num = 1; s_addr = 0;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);
        start = 1; @(posedge clk); start = 0;
        wait (ocnt >= NOUT);
        repeat (10) @(posedge clk);
        for (i = 0; i < NOUT; i = i + 1) begin
            if (outm[i] !== expm[i]) begin
                if (err < 8)
                    $display("[UPS][ERR] idx=%0d got=%032h exp=%032h", i, outm[i], expm[i]);
                err = err + 1;
            end
        end
        $writememh("golden/hw_out_upsample_top.mem", outm);
        if (ocnt == NOUT && err == 0)
            $display("[UPS] TB_PASS  beats=%0d", ocnt);
        else
            $display("[UPS] TB_FAIL  out=%0d/%0d err=%0d", ocnt, NOUT, err);
        $finish;
    end

    initial begin
        #1_000_000;
        $display("[UPS] TB_FAIL  timeout ocnt=%0d", ocnt);
        $finish;
    end

endmodule
