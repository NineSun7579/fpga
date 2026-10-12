// Isolated FPGA V8 activation primitive. Verilog-2001, no vendor IP.
// Program all 256 entries before non-bypass use. Reset does not erase the LUT.
module fpga_v8_activation_lut #(
    parameter LANES = 16
) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 cfg_valid,
    output wire                 cfg_ready,
    input  wire [7:0]           cfg_addr,
    input  wire [7:0]           cfg_data,
    input  wire                 s_valid,
    output wire                 s_ready,
    input  wire [LANES*8-1:0]   s_data,
    input  wire                 s_last,
    input  wire                 bypass,
    output reg                  m_valid,
    input  wire                 m_ready,
    output wire [LANES*8-1:0]   m_data,
    output reg                  m_last
);
    wire output_room;
    wire input_fire;
    wire cfg_fire;

    assign output_room = !m_valid || m_ready;
    // A pending output blocks configuration, even on its consumption edge.
    assign cfg_ready = !rst && !m_valid;
    // Configuration has priority and blocks new input, allowing a drain.
    assign s_ready = !rst && !cfg_valid && output_room;
    assign input_fire = s_valid && s_ready;
    assign cfg_fire = cfg_valid && cfg_ready;

    always @(posedge clk) begin
        if (rst) begin
            m_valid <= 1'b0;
            m_last <= 1'b0;
        end else if (output_room) begin
            m_valid <= input_fire;
            if (input_fire)
                m_last <= s_last;
        end
    end

    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin : lanes
            // Independent synchronous read ports, broadcast synchronous writes.
            // No table reset or initial block, to permit RAM inference.
            reg [7:0] table_mem [0:255];
            reg [7:0] result;
            assign m_data[lane*8 +: 8] = result;
            always @(posedge clk) begin
                if (rst) begin
                    result <= 8'd0;
                end else begin
                    if (cfg_fire)
                        table_mem[cfg_addr] <= cfg_data;
                    if (input_fire) begin
                        if (bypass)
                            result <= s_data[lane*8 +: 8];
                        else
                            result <= table_mem[s_data[lane*8 +: 8]];
                    end
                end
            end
        end
    endgenerate
endmodule
