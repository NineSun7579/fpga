`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Module : sfp_test_src
// Description : SFP 链路测试用内部视频源(不依赖摄像头/DDR 通路)。
//   在 clk 域产生 VGA 类栅格(总栅格 800x525, 有效 640x480), 输出 {vs,hs,de,rgb565}
//   直接喂 sfp_video_tx; vs/hs 为正脉冲, 与像素同拍寄存输出, 保持对齐。
//   PAT=0: 位置编码测试图 pix={y[7:0],x[7:0]} —— 行内每像素恰好 +1, 行尾跳到
//          {y+1,0x00}; 接收端据此校验数据字内 pix1==pix0+1、跨字连续、行边界,
//          用于"光口连通性 + 误码"判定(不依赖画面显示)。
//   PAT=1: 8 色彩条(按 x[9:7], 每条 128 像素), 彩条模式用。
//////////////////////////////////////////////////////////////////////////////////
module sfp_test_src #(
    parameter PAT = 0
)(
    input               clk      ,
    input               rst_n    ,
    output     reg [18:0] vid_data   // {vs,hs,de,rgb565[15:0]}
);

    localparam [11:0] HW = 12'd640;   // 有效宽
    localparam [11:0] HH = 12'd480;   // 有效高
    localparam [11:0] TW = 12'd800;   // 总宽
    localparam [11:0] TH = 12'd525;   // 总高

    reg [11:0] x_cnt, y_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x_cnt <= 12'd0;
            y_cnt <= 12'd0;
        end
        else begin
            if (x_cnt == TW - 12'd1) begin
                x_cnt <= 12'd0;
                y_cnt <= (y_cnt == TH - 12'd1) ? 12'd0 : y_cnt + 12'd1;
            end
            else begin
                x_cnt <= x_cnt + 12'd1;
            end
        end
    end

    // 同步/有效信号(组合产生, 与像素一起打一拍, 对齐关系不变)
    wire vs_w = ((y_cnt == 12'd490) || (y_cnt == 12'd491));
    wire hs_w = (x_cnt >= 12'd656) && (x_cnt < 12'd752);
    wire de_w = (x_cnt < HW) && (y_cnt < HH);

    // 测试图样
    reg [15:0] pix_w;
    always @(*) begin
        if (PAT == 1) begin
            case (x_cnt[9:7])
                3'd0:    pix_w = 16'hF800;  // 红
                3'd1:    pix_w = 16'h07E0;  // 绿
                3'd2:    pix_w = 16'h001F;  // 蓝
                3'd3:    pix_w = 16'hFFE0;  // 黄
                3'd4:    pix_w = 16'hF81F;  // 品红
                3'd5:    pix_w = 16'h07FF;  // 青
                3'd6:    pix_w = 16'hFFFF;  // 白
                default: pix_w = 16'h0000;  // 黑
            endcase
        end
        else begin
            pix_w = {y_cnt[7:0], x_cnt[7:0]};
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            vid_data <= 19'd0;
        else
            vid_data <= {vs_w, hs_w, de_w, pix_w};
    end

endmodule
