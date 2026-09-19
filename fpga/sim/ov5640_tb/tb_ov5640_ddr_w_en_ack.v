`timescale 1ns/1ps

module tb_ov5640_ddr_w_en_ack;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst = 1'b1;
    reg cam_en = 1'b1;
    reg [1:0] pending = 2'b00;
    reg [15:0] s_data = 16'h1234;
    reg s_valid = 1'b0;
    reg s_hsync = 1'b0;
    reg s_vsync = 1'b0;
    wire [15:0] m_data;
    wire m_valid, m_hsync, m_vsync;
    integer syncs = 0;
    integer errors = 0;

    ov5640_ddr_w_en #(.DATA_WIDTH(16)) dut (
        .axi_clk(clk), .axi_rst(rst), .axi_cam_en(cam_en),
        .frame_pending(pending),
        .s_data(s_data), .s_data_valid(s_valid),
        .s_hsync(s_hsync), .s_vsync(s_vsync),
        .m_data(m_data), .m_data_valid(m_valid),
        .m_hsync(m_hsync), .m_vsync(m_vsync)
    );

    always @(posedge clk)
        if (m_vsync) syncs <= syncs + 1;

    task pulse_vsync;
        begin
            @(negedge clk); s_vsync = 1'b1;
            @(negedge clk); s_vsync = 1'b0;
            repeat (5) @(negedge clk);
        end
    endtask

    task check(input integer cond, input [255:0] msg);
        begin
            if (!cond) begin
                errors = errors + 1;
                $display("[FAIL] %0s at %0t", msg, $time);
            end
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst = 1'b0;

        pulse_vsync();
        check(syncs == 1, "first frame accepted");
        @(negedge clk); s_valid = 1'b1;
        @(negedge clk); check(m_valid, "data passes in active frame");
        s_valid = 1'b0;

        // Model the controller raising pending immediately when the frame ends.
        pending = 2'b01;
        pulse_vsync();
        check(syncs == 1, "pending frame blocks next frame");
        @(negedge clk); s_valid = 1'b1;
        @(negedge clk); check(!m_valid, "blocked frame data is dropped");
        s_valid = 1'b0;

        pending = 2'b00;
        @(negedge clk); s_valid = 1'b1;
        @(negedge clk); check(!m_valid, "ack waits for next frame boundary");
        s_valid = 1'b0;
        pulse_vsync();
        check(syncs == 2, "frame accepted after ack");
        @(negedge clk); s_valid = 1'b1;
        @(negedge clk); check(m_valid, "data resumes after ack");
        s_valid = 1'b0;

        if (errors == 0)
            $display("=== TB PASS: ACK flow blocks overwrite ===");
        else
            $display("=== TB FAIL: %0d errors ===", errors);
        $finish;
    end
endmodule
