`timescale 1ns/1ps
// Isolated ready/valid RAW preprocessing; no camera, KF, DDR or board wiring.
module fpga_v8_raw_letterbox #(
    parameter integer WIDTH = 640,
    parameter integer HEIGHT = 480,
    parameter integer OUT_HEIGHT = 640,
    parameter integer TOP_ROWS = 80,
    parameter integer FILL_VALUE = 114
) (
    input wire clk,
    input wire rst_n,
    input wire start_valid,
    output wire start_ready,
    output reg busy,
    output reg done,
    output reg frame_error,
    output wire config_error,
    input wire [15:0] s_data,
    input wire s_valid,
    output wire s_ready,
    input wire s_last,
    output reg [23:0] m_data,
    output reg m_valid,
    input wire m_ready,
    output reg m_last
);
    // Bounded geometry keeps row/column counters and comparisons unsigned.
    // No resize: WIDTH is both the source and output width.
    localparam CONFIG_OK = (WIDTH >= 1) && (WIDTH <= 65535) &&
                            (HEIGHT >= 1) && (HEIGHT <= 65535) &&
                            (OUT_HEIGHT >= HEIGHT) && (OUT_HEIGHT <= 65535) &&
                            (TOP_ROWS >= 0) &&
                            (TOP_ROWS <= OUT_HEIGHT - HEIGHT) &&
                            (FILL_VALUE >= 0) && (FILL_VALUE <= 255);
    reg [15:0] column;
    reg [15:0] row;
    reg generated_all;
    wire body_row;
    wire output_slot;
    wire final_source;
    wire final_output;
    wire [23:0] expanded;

    assign config_error = !CONFIG_OK;
    assign start_ready = rst_n && CONFIG_OK && !busy;
    assign body_row = (row >= TOP_ROWS) && (row < TOP_ROWS + HEIGHT);
    assign output_slot = !m_valid || m_ready;
    assign final_source = (column == WIDTH - 1) &&
                          (row == TOP_ROWS + HEIGHT - 1);
    assign final_output = (column == WIDTH - 1) && (row == OUT_HEIGHT - 1);
    assign s_ready = rst_n && busy && !generated_all && body_row && output_slot;
    // Lane byte 0 is R, then G, then B. Input is an assembled RGB565 word.
    assign expanded = {s_data[4:0], s_data[4:2],
                       s_data[10:5], s_data[10:9],
                       s_data[15:11], s_data[15:13]};

    // Simulation diagnostic plus synthesizable config_error/start rejection.
    // synthesis translate_off
    initial begin
        if (!CONFIG_OK)
            $display("FPGA_V8_RAW_LETTERBOX_INVALID_PARAMETERS");
    end
    // synthesis translate_on

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            frame_error <= 1'b0;
            column <= 16'd0;
            row <= 16'd0;
            generated_all <= 1'b0;
            m_data <= 24'd0;
            m_valid <= 1'b0;
            m_last <= 1'b0;
        end else begin
            done <= 1'b0;
            if (start_valid && start_ready) begin
                busy <= 1'b1;
                frame_error <= 1'b0;
                column <= 16'd0;
                row <= 16'd0;
                generated_all <= 1'b0;
                m_valid <= 1'b0;
                m_last <= 1'b0;
            end else if (busy) begin
                if (m_valid && m_ready && m_last) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
                if (output_slot) begin
                    m_valid <= 1'b0;
                    m_last <= 1'b0;
                    if (!generated_all && (!body_row || s_valid)) begin
                        m_data <= body_row ? expanded : {3{FILL_VALUE[7:0]}};
                        m_valid <= 1'b1;
                        m_last <= final_output;
                        // Check every accepted source marker, but always use
                        // geometry to locate the boundary. Error is sticky.
                        if (body_row && (s_last != final_source))
                            frame_error <= 1'b1;
                        if (final_output)
                            generated_all <= 1'b1;
                        if (column == WIDTH - 1) begin
                            column <= 16'd0;
                            row <= row + 16'd1;
                        end else begin
                            column <= column + 16'd1;
                        end
                    end
                end
            end
        end
    end
endmodule
