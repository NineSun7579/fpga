`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_dvp_rgb565_cdc_staging_pipeline.sv
 * @brief 验证 OV5640 DVP 到双时钟 staging 输出的联合行为。
 */
module tb_ov5640_dvp_rgb565_cdc_staging_pipeline;
    logic in_rst_n=0, out_rst_n=0, cam_pclk=0, out_clk=0;
    logic cam_vsync=0, cam_href=0; logic [7:0] cam_data=0;
    logic out_valid, out_ready=0; logic [31:0] out_data; logic [3:0] out_keep;
    logic out_last; logic [4:0] out_user; logic source_overflow;
    integer beat_count=0;
    integer normal_beat_count=0;
    integer pressure_beat_count=0;
    integer phase=0;

    ov5640_dvp_rgb565_cdc_staging_pipeline #(.FIFO_ADDR_WIDTH(3)) dut (.*);
    always #5ns cam_pclk=~cam_pclk;
    always #7ns out_clk=~out_clk;
    initial begin #30us; $fatal(1, "OV5640 CDC staging timeout"); end

    always @(negedge out_clk) begin
        if (out_rst_n && out_valid && out_ready) begin
            if (phase == 0) begin
                if (beat_count == 0 && (out_keep !== 4'hf || out_user[1:0] !== 2'b11 || out_last))
                    $fatal(1, "CDC staging first beat mismatch");
                if (beat_count == 1 && (out_keep !== 4'h3 || !out_last || !out_user[2]))
                    $fatal(1, "CDC staging final beat mismatch");
                if (beat_count == 2 && (out_keep !== 4'h0 || !out_last || !out_user[3]))
                    $fatal(1, "CDC staging frame-end event mismatch");
                beat_count = beat_count + 1;
            end else begin
                pressure_beat_count = pressure_beat_count + 1;
            end
        end
    end

    task automatic drive_byte(input logic [7:0] value); begin cam_data=value; @(posedge cam_pclk); end endtask
    task automatic drive_pixel(input logic [15:0] value); begin drive_byte(value[15:8]); drive_byte(value[7:0]); end endtask

    initial begin
        repeat(2) @(posedge cam_pclk); in_rst_n=1;
        repeat(2) @(posedge out_clk); out_rst_n=1;
        @(negedge out_clk); out_ready=1;
        @(posedge cam_pclk); cam_vsync=1; @(posedge cam_pclk); cam_vsync=0;
        @(posedge cam_pclk); cam_href=1;
        drive_pixel(16'hf800); drive_pixel(16'h07e0); drive_pixel(16'h001f);
        cam_href=0; @(posedge cam_pclk); cam_vsync=1; @(posedge cam_pclk); cam_vsync=0;
        repeat(20) @(posedge out_clk);
        if (beat_count != 3 || source_overflow)
            $fatal(1, "CDC staging normal path mismatch: beats=%0d overflow=%b", beat_count, source_overflow);
        normal_beat_count = beat_count;

        // 复位后暂停输出，持续输入足够多的 word，验证压力会被明确报告。
        in_rst_n = 1'b0;
        out_rst_n = 1'b0;
        cam_href = 1'b0;
        cam_vsync = 1'b0;
        beat_count = 0;
        pressure_beat_count = 0;
        phase = 1;
        repeat(2) @(posedge cam_pclk);
        repeat(2) @(posedge out_clk);
        in_rst_n = 1'b1;
        out_rst_n = 1'b1;
        @(negedge out_clk); out_ready=1'b0;
        @(posedge cam_pclk); cam_vsync=1'b1; @(posedge cam_pclk); cam_vsync=1'b0;
        @(posedge cam_pclk); cam_href=1'b1;
        for (integer index=0; index<64; index=index+1)
            drive_pixel(16'h4000 + index);
        cam_href=1'b0; @(posedge cam_pclk); cam_vsync=1'b1; @(posedge cam_pclk); cam_vsync=1'b0;
        repeat(20) @(posedge cam_pclk);
        if (!source_overflow)
            $fatal(1, "CDC staging pressure was not reported");
        out_ready=1'b1;
        repeat(40) @(posedge out_clk);
        $display("INFO: normal staging path delivered %0d beats without overflow", normal_beat_count);
        $display("INFO: sustained downstream pressure reported overflow and drained %0d beats", pressure_beat_count);
        $display("TEST PASS"); $finish;
    end
endmodule
`default_nettype wire
