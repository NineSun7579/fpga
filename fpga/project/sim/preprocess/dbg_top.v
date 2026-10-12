`timescale 1ns/1ps
module dbg_top;
    reg clk=0, rst_n=0;
    always #5 clk=~clk;
    // 绑定监视: 记录前12次 FIFO 写/读
    integer wc=0, rc=0;
    always @(posedge clk) begin
        if (rst_n && tb.u_ofifo.wr_en && wc<12) begin
            $display("[W] t=%0t wptr=%0d data=%04h", $time, tb.u_ofifo.wptr, tb.u_ofifo.wr_data);
            wc=wc+1;
        end
        if (rst_n && tb.u_ofifo.rd_en && tb.u_ofifo.rd_valid && rc<12) begin
            $display("[R] t=%0t rptr=%0d data=%04h cnt=%0d", $time, tb.u_ofifo.rptr, tb.u_ofifo.rd_data, tb.u_ofifo.cnt);
            rc=rc+1;
        end
    end
endmodule
