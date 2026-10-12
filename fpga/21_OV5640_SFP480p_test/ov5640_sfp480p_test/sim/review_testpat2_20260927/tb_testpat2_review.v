`timescale 1ns/1ps
module tb_testpat2_review;
reg core_clk=0;
reg ddr_init_done=0;
always #5 core_clk=~core_clk;
    reg  [12:0] tp2_x;
    reg  [9:0]  tp2_y;
    reg  [3:0]  tp2_barx;
    reg  [3:0]  tp2_bar;
    reg  [11:0] tp2_blk;
    wire        tp2_de    = (tp2_y < 10'd480) && (tp2_x < 13'd1280);
    wire        tp2_fsync = (tp2_y == 10'd0) && (tp2_x == 13'd0);

    always @(posedge core_clk) begin
        if (!ddr_init_done) begin
            tp2_x <= 13'd0; tp2_y <= 10'd0; tp2_barx <= 4'd0; tp2_bar <= 4'd0; tp2_blk <= 12'd0;
        end else if (tp2_x == 13'd3199) begin
            tp2_x   <= 13'd0;
            tp2_barx<= 4'd0;
            tp2_bar <= 4'd0;
            if (tp2_y == 10'd519) begin
                tp2_y   <= 10'd0;
                tp2_blk <= (tp2_blk >= 12'd1216) ? 12'd0 : tp2_blk + 12'd16;
            end else begin
                tp2_y <= tp2_y + 10'd1;
            end
        end else begin
            tp2_x <= tp2_x + 13'd1;
            if (tp2_de) begin
                if (tp2_barx == 4'd159) begin tp2_barx <= 4'd0; tp2_bar <= tp2_bar + 4'd1; end
                else                      tp2_barx <= tp2_barx + 4'd1;
            end
        end
    end

    reg [15:0] tp2_bars;
    always @(*) begin
        case (tp2_bar)
            4'd0: tp2_bars = 16'hF800;  // ?
            4'd1: tp2_bars = 16'h07E0;  // ?
            4'd2: tp2_bars = 16'h001F;  // ?
            4'd3: tp2_bars = 16'hFFE0;  // ?
            4'd4: tp2_bars = 16'hF81F;  // ??
            4'd5: tp2_bars = 16'h07FF;  // ?
            4'd6: tp2_bars = 16'hFFFF;  // ?
            default: tp2_bars = 16'h0000;
        endcase
    end
    wire tp2_block = (tp2_x >= tp2_blk) && (tp2_x < (tp2_blk + 12'd64)) &&
                     (tp2_y >= 10'd200) && (tp2_y < 10'd264);
    wire [15:0] tp2_data = tp2_block ? 16'hFFFF : tp2_bars;


integer x, mismatches=0, first_green=-1;
reg [15:0] expected;
initial begin
  repeat(3) @(negedge core_clk);
  ddr_init_done=1;
  for(x=0;x<1280;x=x+1) begin
    case(x/160)
      0: expected=16'hF800;
      1: expected=16'h07E0;
      2: expected=16'h001F;
      3: expected=16'hFFE0;
      4: expected=16'hF81F;
      5: expected=16'h07FF;
      6: expected=16'hFFFF;
      default: expected=0;
    endcase
    if(tp2_data !== expected) mismatches=mismatches+1;
    if(tp2_data==16'h07E0 && first_green<0) first_green=x;
    if(x%16==0 && x<272) $display("PIXEL x=%0d color=%h",x,tp2_data);
    @(negedge core_clk);
  end
  $display("REVIEW_RESULT first_green=%0d expected=160 mismatches=%0d/1280",first_green,mismatches);
  if(mismatches==0) $display("TEST PASS"); else $display("TEST FAIL: source pattern is not 8 bars of 160 pixels");
  $finish;
end
endmodule
