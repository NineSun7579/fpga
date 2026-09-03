`default_nettype none

/**
 * @file rgb565_axis4_mwr_descriptor.sv
 * @brief Convert staging beats into vendor-independent Memory Write requests.
 *
 * @details
 * This module defines a normalized request boundary only. It does not drive
 * PCIe IP, encode TLP headers, or select a host address. Payload beats are
 * held until the downstream request consumer accepts them. Zero-keep control
 * beats complete locally because they carry no bytes to write.
 *
 * @par Interface contract
 * - `req_length_dw` is the actual DWORD count expected by the audited PG2L50H
 *   MWR TX request port. Every emitted request contains one DWORD.
 * - `in_keep==0` is accepted without asserting `req_valid` and does not advance
 *   the byte address.
 * - Partial `in_keep` values remain sideband metadata. This module does not
 *   claim that the vendor TX can encode their byte enables.
 */
module rgb565_axis4_mwr_descriptor #(
    parameter logic [63:0] BASE_ADDR = 64'h0000_0000_0000_0000
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        in_valid,
    output logic             in_ready,
    input  wire logic [31:0] in_data,
    input  wire logic [3:0]  in_keep,
    input  wire logic         in_last,
    input  wire logic         in_frame_end,
    input  wire logic         in_protocol_error,
    output logic             req_valid,
    input  wire logic         req_ready,
    output logic [63:0]       req_addr,
    output logic [9:0]        req_length_dw,
    output logic [31:0]       req_data,
    output logic [3:0]        req_keep,
    output logic              req_last,
    output logic              req_frame_end,
    output logic              req_protocol_error,
    output logic              req_cross_4kb_boundary
);
    logic        active;
    logic [63:0] next_addr;
    logic [31:0] data_reg;
    logic [3:0]  keep_reg;
    logic [2:0]  byte_count_reg;
    logic        last_reg;
    logic        frame_end_reg;
    logic        protocol_error_reg;

    always_comb begin
        in_ready = !active;
        req_valid = active;
        req_addr = next_addr;
        req_length_dw = 10'd1;
        req_data = data_reg;
        req_keep = keep_reg;
        req_last = last_reg;
        req_frame_end = frame_end_reg;
        req_protocol_error = protocol_error_reg;
        req_cross_4kb_boundary = ((next_addr[11:0] + byte_count_reg) > 13'd4096);
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active    <= 1'b0;
            next_addr <= BASE_ADDR;
            data_reg  <= 32'd0;
            keep_reg  <= 4'd0;
            byte_count_reg <= 3'd0;
            last_reg  <= 1'b0;
            frame_end_reg <= 1'b0;
            protocol_error_reg <= 1'b0;
        end else begin
            if (!active && in_valid) begin
                if (in_keep != 4'h0) begin
                    active <= 1'b1;
                    data_reg <= in_data;
                    keep_reg <= in_keep;
                    byte_count_reg <= {2'b0, in_keep[0]} + {2'b0, in_keep[1]} +
                                      {2'b0, in_keep[2]} + {2'b0, in_keep[3]};
                    last_reg <= in_last;
                    frame_end_reg <= in_frame_end;
                    protocol_error_reg <= in_protocol_error;
                end
            end else if (active && req_ready) begin
                active <= 1'b0;
                next_addr <= next_addr + byte_count_reg;
            end
        end
    end
endmodule

`default_nettype wire
