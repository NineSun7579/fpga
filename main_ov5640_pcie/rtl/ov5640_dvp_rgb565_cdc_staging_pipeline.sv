`default_nettype none

/**
 * @file ov5640_dvp_rgb565_cdc_staging_pipeline.sv
 * @brief 将 OV5640 DVP 图像流送入双时钟 staging CDC 边界。
 *
 * @details
 * 数据路径为 DVP 采集、灰度处理、128-bit 打包、两槽 word 短突发缓冲、
 * 4-byte staging adapter，再进入双时钟 CDC bridge。`source_overflow` 用于
 * 暴露 camera-side 短缓冲耗尽的情况；溢出帧以空载、带协议错误的帧尾结束，
 * 当前帧余下内容被丢弃，并从后续 `frame_start` 恢复。
 *
 * @warning
 * 本模块不实例化 DDR3/PCIe IP，也不保证持续满载时无丢帧。持续背压可能
 * 丢弃多个完整帧；FIFO 深度、三域复位、DDR3 回收无效帧和最终帧缓存仍由
 * 产品集成层负责。
 */
module ov5640_dvp_rgb565_cdc_staging_pipeline #(
    parameter logic VSYNC_ACTIVE_LEVEL = 1'b1,
    parameter logic HREF_ACTIVE_LEVEL  = 1'b1,
    parameter logic FIRST_BYTE_IS_HIGH = 1'b1,
    parameter integer FIFO_ADDR_WIDTH  = 4
) (
    input  wire logic        in_rst_n,
    input  wire logic        cam_pclk,
    input  wire logic        cam_vsync,
    input  wire logic        cam_href,
    input  wire logic [7:0]  cam_data,
    input  wire logic        out_rst_n,
    input  wire logic        out_clk,
    output logic             out_valid,
    input  wire logic         out_ready,
    output logic [31:0]      out_data,
    output logic [3:0]       out_keep,
    output logic             out_last,
    output logic [4:0]       out_user,
    output logic             source_overflow
);
    logic word_valid;
    logic [127:0] word_data;
    logic [15:0] word_keep;
    logic word_frame_start, word_line_start, word_line_end;
    logic word_frame_end, word_protocol_error;
    logic skid_in_ready, skid_valid;
    logic [127:0] skid_data;
    logic [15:0] skid_keep;
    logic skid_frame_start, skid_line_start, skid_line_end;
    logic skid_frame_end, skid_protocol_error;
    logic skid_overflow;
    logic adapter_in_ready, adapter_valid;
    logic [127:0] adapter_data;
    logic [3:0] adapter_keep;
    logic adapter_last;
    logic [7:0] adapter_user;
    logic cdc_in_ready;

    ov5640_dvp_rgb565_word_pipeline #(
        .VSYNC_ACTIVE_LEVEL(VSYNC_ACTIVE_LEVEL),
        .HREF_ACTIVE_LEVEL(HREF_ACTIVE_LEVEL),
        .FIRST_BYTE_IS_HIGH(FIRST_BYTE_IS_HIGH)
    ) u_word_pipeline (
        .rst_n(in_rst_n), .cam_pclk(cam_pclk), .cam_vsync(cam_vsync),
        .cam_href(cam_href), .cam_data(cam_data), .word_valid(word_valid),
        .word_data(word_data), .word_keep(word_keep),
        .word_frame_start(word_frame_start), .word_line_start(word_line_start),
        .word_line_end(word_line_end), .word_frame_end(word_frame_end),
        .word_protocol_error(word_protocol_error)
    );

    rgb565_word_skid_buffer u_word_skid_buffer (
        .rst_n(in_rst_n), .clk(cam_pclk), .in_valid(word_valid), .in_ready(skid_in_ready),
        .in_data(word_data), .in_keep(word_keep), .in_frame_start(word_frame_start),
        .in_line_start(word_line_start), .in_line_end(word_line_end),
        .in_frame_end(word_frame_end), .in_protocol_error(word_protocol_error),
        .out_valid(skid_valid), .out_ready(adapter_in_ready), .out_data(skid_data),
        .out_keep(skid_keep), .out_frame_start(skid_frame_start),
        .out_line_start(skid_line_start), .out_line_end(skid_line_end),
        .out_frame_end(skid_frame_end), .out_protocol_error(skid_protocol_error),
        .overflow(skid_overflow)
    );

    rgb565_word_to_axis4_adapter u_axis4_adapter (
        .rst_n(in_rst_n), .clk(cam_pclk), .in_valid(skid_valid),
        .in_ready(adapter_in_ready), .in_data(skid_data), .in_keep(skid_keep),
        .in_frame_start(skid_frame_start), .in_line_start(skid_line_start),
        .in_line_end(skid_line_end), .in_frame_end(skid_frame_end),
        .in_protocol_error(skid_protocol_error), .out_valid(adapter_valid),
        .out_ready(cdc_in_ready), .out_data(adapter_data), .out_keep(adapter_keep),
        .out_last(adapter_last), .out_user(adapter_user)
    );

    rgb565_axis4_cdc_bridge #(.ADDR_WIDTH(FIFO_ADDR_WIDTH)) u_cdc_bridge (
        .in_rst_n(in_rst_n), .in_clk(cam_pclk), .in_valid(adapter_valid),
        .in_ready(cdc_in_ready), .in_data(adapter_data[31:0]), .in_keep(adapter_keep),
        .in_last(adapter_last), .in_user(adapter_user[4:0]), .out_rst_n(out_rst_n),
        .out_clk(out_clk), .out_valid(out_valid), .out_ready(out_ready),
        .out_data(out_data), .out_keep(out_keep), .out_last(out_last),
        .out_user(out_user)
    );

    assign source_overflow = skid_overflow;
endmodule

`default_nettype wire
