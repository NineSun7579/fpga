`default_nettype none

/**
 * @file rgb565_axis4_async_fifo.sv
 * @brief 在独立写入/读出时钟域之间传输 staging beat。
 *
 * @details
 * 这是 main OV5640 工程的板级无关 CDC 合同，不依赖厂商 FIFO IP。
 * 数据包含 32-bit beat、4-bit keep、last 和 5-bit 事件标志。复位只异步
 * 置位本地指针；两个时钟域的复位释放时序由上层集成设计负责。
 *
 * @warning
 * 本模块只证明 FIFO 的数据顺序与满/空握手，不证明具体器件 RAM 推断、
 * CDC 静态工具分类、DDR3 初始化或 PCIe 用户时钟约束。
 */
module rgb565_axis4_async_fifo #(
    parameter integer ADDR_WIDTH = 2
) (
    input  wire logic       wr_rst_n,
    input  wire logic       wr_clk,
    input  wire logic       wr_valid,
    output logic            wr_ready,
    input  wire logic [31:0] wr_data,
    input  wire logic [3:0]  wr_keep,
    input  wire logic         wr_last,
    input  wire logic [4:0]   wr_user,
    input  wire logic       rd_rst_n,
    input  wire logic       rd_clk,
    output logic              rd_valid,
    input  wire logic         rd_ready,
    output logic [31:0]      rd_data,
    output logic [3:0]       rd_keep,
    output logic              rd_last,
    output logic [4:0]       rd_user
);
    localparam integer DEPTH = 1 << ADDR_WIDTH;
    localparam integer PTR_WIDTH = ADDR_WIDTH + 1;
    logic [40:0] storage [0:DEPTH-1];
    logic [PTR_WIDTH-1:0] wr_ptr_bin, wr_ptr_gray;
    logic [PTR_WIDTH-1:0] rd_ptr_bin, rd_ptr_gray;
    logic [PTR_WIDTH-1:0] rd_gray_wr1, rd_gray_wr2;
    logic [PTR_WIDTH-1:0] wr_gray_rd1, wr_gray_rd2;
    logic full_reg, empty_reg;
    logic [PTR_WIDTH-1:0] wr_ptr_bin_next, wr_ptr_gray_next;
    logic [PTR_WIDTH-1:0] rd_ptr_bin_next, rd_ptr_gray_next;
    logic full_next, empty_next;

    function automatic logic [PTR_WIDTH-1:0] bin_to_gray(input logic [PTR_WIDTH-1:0] value);
        bin_to_gray = (value >> 1) ^ value;
    endfunction

    always_comb begin
        wr_ptr_bin_next = wr_ptr_bin + ((wr_valid && !full_reg) ? 1'b1 : 1'b0);
        wr_ptr_gray_next = bin_to_gray(wr_ptr_bin_next);
        rd_ptr_bin_next = rd_ptr_bin + ((!empty_reg && rd_ready) ? 1'b1 : 1'b0);
        rd_ptr_gray_next = bin_to_gray(rd_ptr_bin_next);
        wr_ready = !full_reg;
        rd_valid = !empty_reg;
        full_next = (wr_ptr_gray_next == {~rd_gray_wr2[PTR_WIDTH-1:PTR_WIDTH-2],
                                           rd_gray_wr2[PTR_WIDTH-3:0]});
        empty_next = (rd_ptr_gray_next == wr_gray_rd2);
        rd_data = storage[rd_ptr_bin[ADDR_WIDTH-1:0]][31:0];
        rd_keep = storage[rd_ptr_bin[ADDR_WIDTH-1:0]][35:32];
        rd_last = storage[rd_ptr_bin[ADDR_WIDTH-1:0]][36];
        rd_user = storage[rd_ptr_bin[ADDR_WIDTH-1:0]][40:37];
    end

    always_ff @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            wr_ptr_bin <= '0;
            wr_ptr_gray <= '0;
            rd_gray_wr1 <= '0;
            rd_gray_wr2 <= '0;
            full_reg <= 1'b0;
        end else begin
            rd_gray_wr1 <= rd_ptr_gray;
            rd_gray_wr2 <= rd_gray_wr1;
            if (wr_valid && wr_ready)
                storage[wr_ptr_bin[ADDR_WIDTH-1:0]] <= {wr_user, wr_last, wr_keep, wr_data};
            wr_ptr_bin <= wr_ptr_bin_next;
            wr_ptr_gray <= wr_ptr_gray_next;
            full_reg <= full_next;
        end
    end

    always_ff @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rd_ptr_bin <= '0;
            rd_ptr_gray <= '0;
            wr_gray_rd1 <= '0;
            wr_gray_rd2 <= '0;
            empty_reg <= 1'b1;
        end else begin
            wr_gray_rd1 <= wr_ptr_gray;
            wr_gray_rd2 <= wr_gray_rd1;
            rd_ptr_bin <= rd_ptr_bin_next;
            rd_ptr_gray <= rd_ptr_gray_next;
            empty_reg <= empty_next;
        end
    end
endmodule

`default_nettype wire
