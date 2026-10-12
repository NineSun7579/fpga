`timescale 1ns/1ps
// Exercise the byte-identical production frame-admission block.
module tb_delivery_camera_hold;
    reg clk=0, rst=1, hold=0, busy=0, vs=0, de=1;
    wire valid, sof;
    integer starts=0;
    always #5 clk=~clk;
    ov5640_ddr_w_en #(.DATA_WIDTH(16)) gate (
        .axi_clk(clk),.axi_rst(rst),.capture_stop(1'b0),.axi_cam_en(!hold),
        .frame_pending(2'b00),.engine_busy(busy),.s_data(16'h1234),
        .s_data_valid(de),.s_hsync(1'b0),.s_vsync(vs),
        .m_data(),.m_data_valid(valid),.m_hsync(),.m_vsync(sof));
    always @(posedge clk) if(sof) starts=starts+1;
    task frame_boundary;
        begin
            @(negedge clk); vs=1;
            repeat(5) @(negedge clk);
            vs=0; repeat(5) @(negedge clk);
        end
    endtask
    initial begin
        repeat(4) @(negedge clk); rst=0;
        frame_boundary();
        if(!valid || starts!=1) $fatal(1,"FAIL initial admission");
        // Holding admission mid-frame must allow that frame to drain.
        hold=1; busy=1; repeat(10) @(negedge clk);
        if(!valid || starts!=1) $fatal(1,"FAIL mid-frame hold cancelled data");
        frame_boundary();
        if(valid || starts!=1) $fatal(1,"FAIL held next frame admitted");
        busy=0; repeat(3) frame_boundary();
        if(valid || starts!=1) $fatal(1,"FAIL held idle engine admitted");
        hold=0; repeat(5) @(negedge clk);
        if(valid) $fatal(1,"FAIL release admitted partial frame");
        frame_boundary();
        if(!valid || starts!=2) $fatal(1,"FAIL release did not admit next SOF");
        $display("PASS production camera admission hold/drain/resume");
        $finish;
    end
    initial begin #100000; $fatal(1,"FAIL timeout"); end
endmodule
