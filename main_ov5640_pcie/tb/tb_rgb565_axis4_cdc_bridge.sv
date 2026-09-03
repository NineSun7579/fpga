`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_axis4_cdc_bridge.sv
 * @brief 验证 staging CDC bridge 的跨时钟顺序与事件完整性。
 */
module tb_rgb565_axis4_cdc_bridge;
    logic in_rst_n=0, out_rst_n=0, in_clk=0, out_clk=0;
    logic in_valid=0, in_ready; logic [31:0] in_data=0; logic [3:0] in_keep=0;
    logic in_last=0; logic [4:0] in_user=0;
    logic out_valid, out_ready=0; logic [31:0] out_data; logic [3:0] out_keep;
    logic out_last; logic [4:0] out_user;
    integer received=0;

    rgb565_axis4_cdc_bridge #(.ADDR_WIDTH(3)) dut (
        .in_rst_n(in_rst_n), .in_clk(in_clk), .in_valid(in_valid), .in_ready(in_ready),
        .in_data(in_data), .in_keep(in_keep), .in_last(in_last), .in_user(in_user),
        .out_rst_n(out_rst_n), .out_clk(out_clk), .out_valid(out_valid), .out_ready(out_ready),
        .out_data(out_data), .out_keep(out_keep), .out_last(out_last), .out_user(out_user)
    );
    always #3ns in_clk=~in_clk;
    always #5ns out_clk=~out_clk;
    initial begin #8us; $fatal(1, "CDC bridge timeout"); end

    initial begin
        repeat(3) @(posedge in_clk); in_rst_n=1;
        repeat(2) @(posedge out_clk); out_rst_n=1;
        @(negedge out_clk); out_ready=1;
        for (integer index=0; index<5; index=index+1) begin
            @(negedge in_clk); in_valid=1; in_data=32'h2000+index; in_keep=4'hf;
            in_last=(index==4); in_user={(index==4),3'b000,(index==0)};
            while (!in_ready) @(posedge in_clk);
            @(posedge in_clk); #1ns; in_valid=0;
        end
        while (received<5) @(posedge out_clk);
        repeat(3) @(posedge out_clk);
        if (out_valid) $fatal(1, "CDC bridge did not drain");
        $display("INFO: staging CDC bridge data and event ordering verified");
        $display("TEST PASS"); $finish;
    end

    // 在接收沿前的下降沿检查稳定数据，随后允许下一次接收沿完成握手。
    always @(negedge out_clk) begin
        if (out_rst_n && !out_ready && out_valid) begin
            out_ready=1;
        end
        if (out_rst_n && out_valid && out_ready) begin
            if (out_data !== 32'h2000+received || out_keep !== 4'hf ||
                out_last !== (received==4) || out_user[0] !== (received==0) ||
                out_user[4] !== (received==4))
                $fatal(1, "CDC bridge mismatch: index=%0d data=%h keep=%h last=%b user=%b",
                       received, out_data, out_keep, out_last, out_user);
            received=received+1;
        end
    end
endmodule
`default_nettype wire
