`default_nettype none

/**
 * @file rgb565_axis4_pcie_mwr_bridge.sv
 * @brief Map one normalized write request to the audited PCIe request pins.
 *
 * @details
 * This bridge is intentionally outside the vendor PCIe hierarchy. The
 * request level remains asserted until the controller acknowledges it, while
 * address, length, data, and byte enables remain stable. The byte-enable
 * mapping is provisional because the audited controller exposes no request
 * keep port; a later approved bridge may replace this module.
 */
module rgb565_axis4_pcie_mwr_bridge (
    input  wire logic        rst_n,
    input  wire logic        clk,
    input  wire logic        in_valid,
    output logic             in_ready,
    input  wire logic [63:0] in_addr,
    input  wire logic [9:0]  in_length_dw_minus1,
    input  wire logic [31:0] in_data,
    input  wire logic [3:0]  in_keep,
    input  wire logic        in_cross_4kb_boundary,
    output logic             mwr32_req,
    input  wire logic        mwr32_req_ack,
    output logic [9:0]       req_length,
    output logic [63:0]      req_addr,
    output logic [31:0]      req_data,
    output logic [3:0]       req_keep,
    output logic             cross_4kb_boundary,
    output logic             busy
);
    logic [9:0]  length_reg;
    logic [63:0] addr_reg;
    logic [31:0] data_reg;
    logic [3:0]  keep_reg;
    logic        boundary_reg;

    always_comb begin
        in_ready = !busy;
        mwr32_req = busy;
        req_length = length_reg;
        req_addr = addr_reg;
        req_data = data_reg;
        req_keep = keep_reg;
        cross_4kb_boundary = boundary_reg;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            length_reg <= 10'd0;
            addr_reg <= 64'd0;
            data_reg <= 32'd0;
            keep_reg <= 4'd0;
            boundary_reg <= 1'b0;
        end else if (!busy && in_valid) begin
            busy <= 1'b1;
            length_reg <= in_length_dw_minus1;
            addr_reg <= in_addr;
            data_reg <= in_data;
            keep_reg <= in_keep;
            boundary_reg <= in_cross_4kb_boundary;
        end else if (busy && mwr32_req_ack) begin
            busy <= 1'b0;
        end
    end
endmodule

`default_nettype wire
