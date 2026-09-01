module axis128_bar2_ram #(
    parameter ADDR_WIDTH = 11
) (
    input                  wr_clk,
    input                  wr_rst_n,
    input                  axis_valid,
    output                 axis_ready,
    input      [127:0]     axis_data,
    input                  rd_clk,
    input      [ADDR_WIDTH-1:0] rd_addr,
    output reg [127:0]     rd_data
);

localparam DEPTH = 1 << ADDR_WIDTH;
reg [127:0] mem [0:DEPTH-1];
reg [ADDR_WIDTH-1:0] wr_addr;

assign axis_ready = 1'b1;

always @(posedge wr_clk or negedge wr_rst_n) begin
    if (!wr_rst_n)
        wr_addr <= {ADDR_WIDTH{1'b0}};
    else if (axis_valid) begin
        mem[wr_addr] <= axis_data;
        wr_addr <= wr_addr + 1'b1;
    end
end

always @(posedge rd_clk)
    rd_data <= mem[rd_addr];

endmodule
