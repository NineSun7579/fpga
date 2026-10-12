`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company : Meyesemi demo modified
// Module  : sfp_video_tx
//
// Description :  640x480@60 RGB565 ƵΪ HSST(8B10B) ,
//                SFP0(0, HSST CH2) ͡
//
// ============================ ·Э (նʵ) =====================
//  ·: HSST CH2, 5Gbps, 8B10B, fabric ӿ 32bit @ 125MHz (ʱӼ o_p_clk2core_tx_2)
//  ֽ: i_txd_2[7:0] Ϊϵһֽ (byte0), byte3 ͡
//  txk[n]  1 ʾӦֽΪ K 롣ն K28.5 (0xBC) ֶ,
//   rxk[3:0] :
//
//  1)  (rxk == 4'b0000) -- Я 2 Ч:
//        txd = {pix1[15:0], pix0[15:0]}
//        byte0/1 = ȷ pix0 (RGB565: bit15..11=R, bit10..5=G, bit4..0=B)
//        byte2/3 =  pix1
//        ÿյһ => de Ч,  pix0pix1
//
//  2)  (rxk == 4'b1001) -- /״̬, Я:
//        txd = {8'hBC, {de,hs,vs,5'b0}, 8'h28, 8'hBC}
//        byte0 = K28.5 (, ֶ)
//        byte1 = D28.2 (0x28,  GE ģʽ CTC  skip )
//        byte2 = ״̬: bit0=de, bit1=hs, bit2=vs ( de Ϊ 0)
//        byte3 = D21.5 (0x55)
//        vs/hs ƽ״ֽ̬; ڼͿ֡
//
//  նع:  =>  2  (de=1);  => ,
//   vs/hs ƽ߽֡ vs Ϊ׼, ÿ֡ 640x480 Чء
// ==============================================================================
//////////////////////////////////////////////////////////////////////////////////
`define UD #1

module sfp_video_tx (
    //  (25MHz)
    input                    vid_clk        ,   // ʱ (PLL clkout0, 25MHz)
    input                    vid_rst_n      ,
    input  [18:0]            vid_data       ,   // {vs,hs,de,rgb565[15:0]}
    // fabric  (125MHz, HSST o_p_clk2core_tx_2)
    input                    fab_clk        ,
    input                    fab_rst_n      ,
    input                    link_ready     ,   // HSST PLL lock & TX lane done (free_clk )
    output reg [31:0]        txd            ,   // -> i_txd_2
    output reg [3:0]         txk                // -> i_txk_2
);

    //--------------------------------------------------------------------------
    // ʱ FIFO: 25M  -> 125M 
    //   empty ΪĴ; ֻҪǿÿĵһ, ͬɡ
    //--------------------------------------------------------------------------
    wire                     fifo_empty;
    wire [18:0]              fifo_rdata;
    wire                     fifo_pop = ~fifo_empty;  

    video_async_fifo #(
        .WIDTH (19),
        .DEPTH (512)
    ) u_fifo (
        .wr_clk   (vid_clk      ),
        .wr_rst_n (vid_rst_n    ),
        .wr_en    (1'b1         ),
        .wr_data  (vid_data     ),
        .full     (             ),
        .rd_clk   (fab_clk      ),
        .rd_rst_n (fab_rst_n    ),
        .rd_en    (fifo_pop     ),
        .rd_data  (fifo_rdata   ),
        .empty    (fifo_empty   )
    );

    //--------------------------------------------------------------------------
    // link_ready ͬ fabric 
    //--------------------------------------------------------------------------
    reg [1:0] ready_sync;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n)
            ready_sync <= `UD 2'b00;
        else
            ready_sync <= `UD {ready_sync[0], link_ready};
    end
    wire tx_go = ready_sync[1];

    //--------------------------------------------------------------------------
    // ״̬
    //   vid_data = {vs,hs,de,pix}: de=1 ;
    //   de=0 ֽȡ vs/hs ״̬; FIFO շп֡
    //--------------------------------------------------------------------------
    wire head_vs = fifo_rdata[18];
    wire head_hs = fifo_rdata[17];
    wire head_de = fifo_rdata[16];

    reg        pix_pend;                       // 
    reg [15:0] pix0;
    reg wait_frame; // Drain continuously; resume payload at a consumed VS blank.

    // : byte3=K28.5, byte2=״̬(vs@[21]/hs@[22]), byte1=D28.2, byte0=K28.5
    wire [31:0] ctrl_word = {8'hBC, 1'b0, head_hs, head_vs, 5'b0, 8'h28, 8'hBC};
    wire [3:0]  ctrl_k    = 4'b1001;
    // Rev3.1fix2: idle Я vs/hs -- 37Mд125M, FIFOڳ̬ſ,
    // ְ vs/hs  0, նеƽë, мҡ
    reg  last_vs, last_hs;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n) begin
            last_vs <= 1'b0;
            last_hs <= 1'b0;
        end
        else if (fifo_pop) begin
            last_vs <= `UD head_vs;
            last_hs <= `UD head_hs;
        end
    end
    wire [31:0] idle_word = {8'hBC, 1'b0, last_hs, last_vs, 5'b0, 8'h28, 8'hBC};

    // [CTC FIX] FIFO pop control: pause at skip beat

    // [Rev4.3 2026-09-30] DIAG ģʽƳ: ָԭЭƵ ( 100H sfp_video_rx )

    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n) begin
            txd        <= `UD idle_word;
            txk        <= `UD 4'b1001;
            pix_pend   <= `UD 1'b0;
            pix0       <= `UD 16'b0;
            wait_frame <= `UD 1'b1;
        end
        else begin
            if (!tx_go) begin
                // ·δ: ֻп (FIFO  empty )
                txd <= `UD (fifo_pop ? ctrl_word : idle_word);
                txk <= `UD 4'b1001;
                pix_pend <= `UD 1'b0;
                wait_frame <= `UD 1'b1;
            end
            else if (fifo_pop) begin
                if (wait_frame) begin
                    txd <= `UD ctrl_word;
                    txk <= `UD ctrl_k;
                    pix_pend <= `UD 1'b0;
                    if (head_vs && !head_de)
                        wait_frame <= `UD 1'b0;
                end
                else if (!pix_pend) begin
                    if (head_de) begin
                        pix_pend <= `UD 1'b1;      // ǰ, 
                        pix0     <= `UD fifo_rdata[15:0];
                    end
                    txd <= `UD ctrl_word;          // ڼ䷢(Я vs/hs)
                    txk <= `UD ctrl_k;
                end
                else begin
                    pix_pend <= `UD 1'b0;          // Rev3.1fix1: ַ(ԭ head_de ʹ pix0 , żظ); βԶ
                    if (head_de) begin
                        txd <= `UD {fifo_rdata[15:0], pix0};  // : {pix1,pix0}
                        txk <= `UD 4'b0000;
                    end
                    else begin
                        txd <= `UD ctrl_word;
                        txk <= `UD ctrl_k;
                    end
                end
            end
            else begin
                txd <= `UD idle_word;              // FIFO : п
                txk <= `UD 4'b1001;
            end
        end
    end

endmodule
