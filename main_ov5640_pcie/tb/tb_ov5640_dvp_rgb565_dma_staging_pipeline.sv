`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_ov5640_dvp_rgb565_dma_staging_pipeline.sv
 * @brief 联合验证 OV5640 DVP 到 staging beat/帧描述符的公开行为。
 *
 * @details
 * 驱动三像素小帧，检查两个 staging beat、6 个有效字节、帧尾描述符和
 * 协议错误传播；不验证 DDR3、PCIe TLP、CDC 或主机协议。
 */
module tb_ov5640_dvp_rgb565_dma_staging_pipeline;
    logic rst_n=1'b0, cam_pclk=1'b0, cam_vsync=1'b0, cam_href=1'b0;
    logic [7:0] cam_data=8'h0;
    logic staging_valid, staging_ready=1'b1; logic [127:0] staging_data;
    logic [3:0] staging_keep; logic staging_last; logic [7:0] staging_user;
    logic desc_valid, desc_ready=1'b0; logic [31:0] desc_bytes, desc_beats;
    logic desc_protocol_error; int unsigned staging_count, desc_count;
    ov5640_dvp_rgb565_dma_staging_pipeline dut (.*);
    always #5ns cam_pclk=~cam_pclk;

    always @(posedge cam_pclk) begin
        #1ns;
        if (staging_valid && staging_ready) begin
            $display("INFO: staging beat %0d keep=%h last=%b user=%h", staging_count,
                staging_keep, staging_last, staging_user);
            if (staging_count == 0 && (staging_keep !== 4'hf || staging_user[1:0] !== 2'b11 || staging_last)) $fatal(1,"First staging beat mismatch");
            if (staging_count == 1 && (staging_keep !== 4'h3 || !staging_last || staging_user[2] !== 1'b1)) $fatal(1,"Last staging beat mismatch");
            staging_count=staging_count+1;
        end
        if (desc_valid && desc_ready) begin
            $display("INFO: descriptor handshake bytes=%0d beats=%0d error=%b",
                desc_bytes, desc_beats, desc_protocol_error);
            if (desc_bytes !== 32'd6 || desc_beats !== 32'd2 || desc_protocol_error) $fatal(1,"Frame descriptor mismatch");
            desc_count=desc_count+1;
        end
    end

    task automatic drive_byte(input logic [7:0] value); begin cam_data=value; @(posedge cam_pclk); end endtask
    task automatic drive_pixel(input logic [15:0] value); begin drive_byte(value[15:8]); drive_byte(value[7:0]); end endtask

    initial begin #30us; $fatal(1,"OV5640 staging integration timeout"); end
    initial begin
        staging_count=0; desc_count=0; repeat(2) @(posedge cam_pclk); rst_n=1'b1; @(posedge cam_pclk);
        cam_vsync=1'b1; @(posedge cam_pclk); cam_vsync=1'b0; @(posedge cam_pclk);
        cam_href=1'b1; drive_pixel(16'hf800); drive_pixel(16'h07e0); drive_pixel(16'h001f);
        cam_href=1'b0; @(posedge cam_pclk); cam_vsync=1'b1; @(posedge cam_pclk); cam_vsync=1'b0;
        repeat(4) @(posedge cam_pclk); desc_ready=1'b1;
        repeat(20) begin
            @(posedge cam_pclk);
            if (desc_count == 1) break;
        end
        if(staging_count != 2 || desc_count != 1) $fatal(1,"Integration count mismatch: beats=%0d desc=%0d",staging_count,desc_count);
        $display("INFO: OV5640 DVP to staging beats and frame descriptor verified");
        $display("TEST PASS"); $finish;
    end
endmodule

`default_nettype wire
