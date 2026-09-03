`default_nettype none

/**
 * @file rgb565_axis4_ddr3_write_descriptor.sv
 * @brief Convert one staging beat to a normalized 128-bit DDR write record.
 *
 * @details
 * The address is an opaque 28-bit token and the record is always a single
 * beat. This module does not assume the vendor controller address unit,
 * initialization behavior, or AXI4 burst semantics.
 */
module rgb565_axis4_ddr3_write_descriptor #(
    parameter logic [27:0] BASE_ADDR = 28'd0
) (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        in_valid,
    output logic             in_ready,
    input  wire logic [31:0] in_data,
    input  wire logic [3:0]  in_keep,
    input  wire logic        in_last,
    input  wire logic        in_frame_end,
    input  wire logic        in_protocol_error,
    output logic             write_valid,
    input  wire logic         write_ready,
    output logic [27:0]       write_addr,
    output logic [3:0]        write_awlen,
    output logic [127:0]      write_data,
    output logic [15:0]       write_strb,
    output logic              write_last,
    output logic              write_frame_end,
    output logic              write_protocol_error
);
    logic active;
    logic [27:0] addr_reg;
    logic [31:0] data_reg;
    logic [3:0] keep_reg;
    logic last_reg, frame_end_reg, protocol_error_reg;

    always_comb begin
        in_ready = !active;
        write_valid = active;
        write_addr = addr_reg;
        write_awlen = 4'd0;
        write_data = {96'd0, data_reg};
        write_strb = {12'd0, keep_reg};
        write_last = last_reg;
        write_frame_end = frame_end_reg;
        write_protocol_error = protocol_error_reg;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 1'b0;
            addr_reg <= BASE_ADDR;
            data_reg <= 32'd0;
            keep_reg <= 4'd0;
            last_reg <= 1'b0;
            frame_end_reg <= 1'b0;
            protocol_error_reg <= 1'b0;
        end else if (!active && in_valid) begin
            active <= 1'b1;
            data_reg <= in_data;
            keep_reg <= in_keep;
            last_reg <= in_last;
            frame_end_reg <= in_frame_end;
            protocol_error_reg <= in_protocol_error;
        end else if (active && write_ready) begin
            active <= 1'b0;
            addr_reg <= addr_reg + 28'd1;
        end
    end
endmodule

`default_nettype wire
