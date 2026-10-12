`timescale 1ns/1ps
module expr_test;
    reg [7:0] w00=8'h21, w01=8'h55, w02=8'h37, w10=8'h75, w11=8'hc3,
              w12=8'h54, w20=8'h4a, w21=8'h08, w22=8'hba;
    wire signed [10:0] gx = -( $signed({1'b0,w00}) ) + ( $signed({1'b0,w02}) )
                           - ( $signed({2'b0,w10}) ) + ( $signed({2'b0,w12}) )
                           - ( $signed({1'b0,w20}) ) + ( $signed({1'b0,w22}) );
    wire signed [10:0] gy = -( $signed({1'b0,w00}) ) - ( $signed({2'b0,w01}) )
                           - ( $signed({1'b0,w02}) )
                           + ( $signed({1'b0,w20}) ) + ( $signed({2'b0,w21}) )
                           + ( $signed({1'b0,w22}) );
    initial begin
        #1;
        $display("gx=%0d (期望68)  gy=%0d (期望18)", gx, gy);
        $finish;
    end
endmodule
