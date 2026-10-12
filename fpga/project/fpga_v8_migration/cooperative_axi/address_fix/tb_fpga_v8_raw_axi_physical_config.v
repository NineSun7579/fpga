`timescale 1ns/1ps
module tb_fpga_v8_raw_axi_physical_config;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst_n = 0, cmd_valid = 0;
    wire [7:0] cmd_ready, cmd_error, busy, done, error, arvalid, awvalid, wvalid;
    genvar n;
    generate for (n = 0; n < 8; n = n + 1) begin: invalid_config
        // Four geometry failures, then zero/unaligned/512 MiB limits and a
        // valid aligned limit that is too small for the bus footprint.
        localparam [31:0] TEST_LIMIT = n == 4 ? 32'd0 :
                                         n == 5 ? 32'h08000001 :
                                         n == 6 ? 32'h20000000 :
                                         n == 7 ? 32'h00000010 : 32'h10000000;
        fpga_v8_raw_frame_axi_physical #(
            .WIDTH(n == 0 ? 0 : n == 3 ? 65535 : 4),
            .HEIGHT(n == 3 ? 65535 : 3),
            .OUT_HEIGHT(n == 1 ? 2 : n == 3 ? 65535 : 5),
            .TOP_ROWS(n == 2 ? 3 : 0), .DDR_ADDRESS_LIMIT(TEST_LIMIT)
        ) dut (
            .clk(clk), .rst_n(rst_n), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready[n]),
            .cmd_src_addr(32'h1000), .cmd_dst_addr(32'h01000000), .cmd_frame_id(32'h1234),
            .cmd_error(cmd_error[n]), .busy(busy[n]), .done(done[n]), .error(error[n]),
            .m_axi_read_arvalid(arvalid[n]), .m_axi_read_arready(1'b1),
            .m_axi_read_rid(4'd1), .m_axi_read_rdata(128'd0), .m_axi_read_rresp(2'd0),
            .m_axi_read_rlast(1'b1), .m_axi_read_rvalid(1'b0),
            .m_axi_write_awvalid(awvalid[n]), .m_axi_write_awready(1'b1),
            .m_axi_write_wvalid(wvalid[n]), .m_axi_write_wready(1'b1),
            .m_axi_write_bid(4'd1), .m_axi_write_bresp(2'd0), .m_axi_write_bvalid(1'b0)
        );
        // Check CONFIG_OK itself: otherwise addresses outside a bad limit
        // could reject even if the illegal override were silently accepted.
        initial begin
            #1;
            if (dut.CONFIG_OK !== 1'b0)
                $fatal(1, "invalid parameter configuration accepted: case=%0d limit=%h", n, TEST_LIMIT);
            $display("CONFIG_REJECT_PASS case=%0d limit=%h", n, TEST_LIMIT);
        end
    end endgenerate
    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        if (cmd_ready !== 8'hff) $fatal(1, "invalid configurations must accept rejection");
        cmd_valid = 1;
        @(posedge clk); #2;
        if (cmd_error !== 8'hff || error !== 8'hff || busy !== 0 || done !== 0 ||
            arvalid !== 0 || awvalid !== 0 || wvalid !== 0)
            $fatal(1, "invalid configuration not rejected before AXI traffic");
        @(negedge clk); cmd_valid = 0;
        repeat (5) begin
            @(posedge clk); #2;
            if (cmd_error !== 0 || error !== 8'hff || cmd_ready !== 8'hff ||
                busy !== 0 || done !== 0 || arvalid !== 0 || awvalid !== 0 || wvalid !== 0)
                $fatal(1, "invalid configuration pulse/sticky/idle contract");
        end
        $display("AXI_PHYSICAL_CONFIG_PASS cases=8");
        $finish;
    end
endmodule
