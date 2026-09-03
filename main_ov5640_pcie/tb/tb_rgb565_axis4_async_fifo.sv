`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_async_fifo.sv
 * @brief 验证 staging beat 异步 FIFO 的顺序、满/空和背压合同。
 */
module tb_rgb565_axis4_async_fifo;
    logic wr_rst_n=0, rd_rst_n=0, wr_clk=0, rd_clk=0;
    logic wr_valid=0, wr_ready; logic [31:0] wr_data; logic [3:0] wr_keep;
    logic wr_last; logic [4:0] wr_user;
    logic rd_valid, rd_ready=0; logic [31:0] rd_data; logic [3:0] rd_keep;
    logic rd_last; logic [4:0] rd_user;
    integer received=0;
    rgb565_axis4_async_fifo #(.ADDR_WIDTH(2)) dut (
        .wr_rst_n(wr_rst_n), .wr_clk(wr_clk), .wr_valid(wr_valid), .wr_ready(wr_ready),
        .wr_data(wr_data), .wr_keep(wr_keep), .wr_last(wr_last), .wr_user(wr_user),
        .rd_rst_n(rd_rst_n), .rd_clk(rd_clk), .rd_valid(rd_valid), .rd_ready(rd_ready),
        .rd_data(rd_data), .rd_keep(rd_keep), .rd_last(rd_last), .rd_user(rd_user)
    );
    always #4ns wr_clk=~wr_clk;
    always #7ns rd_clk=~rd_clk;
    initial begin #5us; $fatal(1, "async FIFO timeout"); end

    always @(posedge wr_clk) begin
        if (wr_rst_n && wr_valid && wr_ready)
            $display("INFO: write accepted data=%h", wr_data);
    end

    initial begin
        wr_user=0; wr_data=0; wr_keep=0; wr_last=0;
        repeat(3) @(posedge wr_clk); wr_rst_n=1;
        repeat(3) @(posedge rd_clk); rd_rst_n=1;
        for (integer index=0; index<6; index=index+1) begin
            @(negedge wr_clk); wr_valid=1; wr_data=32'h1000+index; wr_keep=4'hf;
            wr_last=(index==5); wr_user={index[0],4'h0};
            while (!wr_ready) @(posedge wr_clk);
            @(posedge wr_clk); #1ns; wr_valid=0;
        end
        while (received<6) @(posedge rd_clk);
        repeat(3) @(posedge rd_clk);
        if (rd_valid)
            $fatal(1, "async FIFO did not reach empty state");
        $display("INFO: async staging FIFO order and handshake verified");
        $display("TEST PASS"); $finish;
    end

    // 先在下降沿检查稳定数据，再让下一次上升沿完成一次接受，避免组合读口
    // 在接受沿后立即切换而影响验证采样。
    always @(negedge rd_clk) begin
        if (rd_rst_n && !rd_ready && rd_valid) begin
            if (rd_data !== 32'h1000+received || rd_keep !== 4'hf)
                $fatal(1, "async FIFO ordering mismatch: index=%0d data=%h keep=%h last=%b",
                       received, rd_data, rd_keep, rd_last);
            received=received+1;
            rd_ready=1;
        end else if (rd_ready) begin
            rd_ready=0;
        end
    end
endmodule
`default_nettype wire
