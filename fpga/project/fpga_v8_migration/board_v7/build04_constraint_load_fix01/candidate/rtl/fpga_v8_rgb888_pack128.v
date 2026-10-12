`timescale 1ns/1ps
// Byte-stream packer: input {B,G,R}; lane 0 of each output word is first byte.
module fpga_v8_rgb888_pack128 (
    input wire clk,
    input wire rst_n,
    input wire [23:0] s_data,
    input wire s_valid,
    output wire s_ready,
    input wire s_last,
    output reg [127:0] m_data,
    output reg [15:0] m_keep,
    output reg m_valid,
    input wire m_ready,
    output reg m_last
);
    reg [127:0] carry_bytes;
    reg [4:0] byte_count;
    reg flush_pending;
    wire output_slot;
    wire [143:0] appended;
    wire [5:0] appended_count;
    wire [15:0] partial_keep;

    assign output_slot = !m_valid || m_ready;
    // Finish a frame before accepting the next one. A final overflow may
    // need two output words: a full word followed by 1 or 2 remaining bytes.
    assign s_ready = rst_n && output_slot && !flush_pending &&
                     !(m_valid && m_last);
    assign appended = {16'd0, carry_bytes} |
                      ({120'd0, s_data} << (byte_count * 8));
    assign appended_count = {1'b0, byte_count} + 6'd3;
    assign partial_keep = (16'hffff >> (16 - appended_count));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            carry_bytes <= 128'd0;
            byte_count <= 5'd0;
            flush_pending <= 1'b0;
            m_data <= 128'd0;
            m_keep <= 16'd0;
            m_valid <= 1'b0;
            m_last <= 1'b0;
        end else if (output_slot) begin
            m_valid <= 1'b0;
            m_last <= 1'b0;
            m_keep <= 16'd0;
            if (flush_pending) begin
                m_data <= carry_bytes;
                m_keep <= (16'hffff >> (16 - byte_count));
                m_valid <= 1'b1;
                m_last <= 1'b1;
                carry_bytes <= 128'd0;
                byte_count <= 5'd0;
                flush_pending <= 1'b0;
            end else if (s_valid && s_ready) begin
                if (appended_count >= 16) begin
                    m_data <= appended[127:0];
                    m_keep <= 16'hffff;
                    m_valid <= 1'b1;
                    m_last <= s_last && (appended_count == 16);
                    carry_bytes <= {112'd0, appended[143:128]};
                    byte_count <= appended_count - 16;
                    flush_pending <= s_last && (appended_count != 16);
                end else if (s_last) begin
                    m_data <= appended[127:0];
                    m_keep <= partial_keep;
                    m_valid <= 1'b1;
                    m_last <= 1'b1;
                    carry_bytes <= 128'd0;
                    byte_count <= 5'd0;
                end else begin
                    carry_bytes <= appended[127:0];
                    byte_count <= appended_count[4:0];
                end
            end
        end
    end
endmodule
