`timescale 1ns/1ps
module expr_test2;
    reg [7:0] w00=8'h21, w01=8'h55, w02=8'h37, w10=8'h75, w11=8'hc3,
              w12=8'h54, w20=8'h4a, w21=8'h08, w22=8'hba;
    wire signed [10:0] t00 = -( $signed({1'b0,w00}) );
    wire signed [10:0] t02 = ( $signed({1'b0,w02}) );
    wire signed [10:0] t10 = -( $signed({2'b0,w10}) );
    wire signed [10:0] t12 = ( $signed({2'b0,w12}) );
    wire signed [10:0] t20 = -( $signed({1'b0,w20}) );
    wire signed [10:0] t22 = ( $signed({1'b0,w22}) );
    wire signed [10:0] gx_split = t00 + t02 + t10 + t12 + t20 + t22;
    // 直接一条表达式
    wire signed [10:0] gx_chain = -( $signed({1'b0,w00}) ) + ( $signed({1'b0,w02}) )
                           - ( $signed({2'b0,w10}) ) + ( $signed({2'b0,w12}) )
                           - ( $signed({1'b0,w20}) ) + ( $signed({1'b0,w22}) );
    // 常量折叠测试
    wire signed [10:0] neg21 = -( $signed({1'b0,8'h21}) );
    wire signed [10:0] dbl75 = -( $signed({2'b0,8'h75}) );
    initial begin
        #1;
        $display("t00=%0d t02=%0d t10=%0d t12=%0d t20=%0d t22=%0d", t00,t02,t10,t12,t20,t22);
        $display("split=%0d chain=%0d neg21=%0d dbl75=%0d", gx_split, gx_chain, neg21, dbl75);
        $finish;
    end
endmodule
