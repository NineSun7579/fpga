`default_nettype none

/**
 * @file rgb565_axis4_ddr3_write_descriptor.sv
 * @brief 按帧槽分配生成规范化 128-bit DDR3 写记录。
 *
 * @details
 * 模块先接受一个槽号和 opaque 槽基 token，再接受该帧的 staging 记录。
 * 每条记录保持到下游写接口接受，地址在槽内按 `ADDR_STEP` 推进。若帧记录数
 * 超过分配描述符携带的容量，地址停在本槽最后一个 token，越界记录强制标记
 * 协议错误并继续消费到帧尾，避免写入另一槽。模块不解释厂商 DDR3 地址单位、
 * 初始化、burst 或持久化语义。
 *
 * @par Interface contract
 * - `frame_alloc_valid && frame_alloc_ready` 接受一帧的 slot ID 与槽基 token。
 * - `frame_alloc_record_capacity` 与分配字段同拍接受，作为该帧唯一容量合同。
 * - 未持有槽分配时 `in_ready=0`；每帧必须先分配再输入记录。
 * - `in_valid && in_ready` 锁存一条记录；输出在 `write_valid && write_ready`
 *   前保持所有字段稳定。
 * - 帧内所有写记录携带同一 `write_slot_id`，首记录地址等于分配槽基 token。
 * - 容量内记录按 `ADDR_STEP` 推进；越界记录复用本槽末 token 并强制错误。
 * - 帧尾写记录被接受后清除当前槽，随后才允许接受下一帧分配。
 *
 * @par Clock and reset
 * - Clock: `clk`，上升沿。
 * - Reset: `rst_n`，低有效异步断言；集成层必须相对 `clk` 同步释放。
 *
 * @par Assumptions
 * - `ADDR_STEP` 与槽基 token 的物理含义由外部 DDR3 适配层统一定义。
 * - 分配后的输入记录按帧顺序到达，且最终提供一个 `in_frame_end`。
 * - 两个槽的地址范围不重叠由集成层参数合同保证。
 *
 * @warning
 * 越界后的重复尾 token 仅用于把错误帧安全收敛到 drop；该帧数据不可提交。
 */
module rgb565_axis4_ddr3_write_descriptor #(
    parameter logic [27:0] ADDR_STEP = 28'd1
) (
    input  wire logic         rst_n,
    input  wire logic         clk,
    input  wire logic         frame_alloc_valid,
    output logic              frame_alloc_ready,
    input  wire logic         frame_alloc_slot_id,
    input  wire logic [27:0]  frame_alloc_base_addr,
    input  wire logic [31:0]  frame_alloc_record_capacity,
    input  wire logic         in_valid,
    output logic              in_ready,
    input  wire logic [31:0]  in_data,
    input  wire logic [3:0]   in_keep,
    input  wire logic         in_last,
    input  wire logic         in_frame_end,
    input  wire logic         in_protocol_error,
    output logic              write_valid,
    input  wire logic         write_ready,
    output logic              write_slot_id,
    output logic [27:0]       write_addr,
    output logic [3:0]        write_awlen,
    output logic [127:0]      write_data,
    output logic [15:0]       write_strb,
    output logic              write_last,
    output logic              write_frame_end,
    output logic              write_protocol_error
);
    logic        frame_active_reg;
    logic        record_active_reg;
    logic        frame_slot_id_reg;
    logic [27:0] next_addr_reg;
    logic [31:0] frame_capacity_reg;
    logic [31:0] record_count_reg;
    logic        capacity_exceeded_reg;

    logic        record_slot_id_reg;
    logic [27:0] record_addr_reg;
    logic [31:0] data_reg;
    logic [3:0]  keep_reg;
    logic        last_reg;
    logic        frame_end_reg;
    logic        protocol_error_reg;

    initial begin : p_validate_parameters
        if (ADDR_STEP == 28'd0)
            $fatal(1, "DDR3 write descriptor ADDR_STEP must be non-zero");
    end

    always_comb begin
        frame_alloc_ready = !frame_active_reg && !record_active_reg;
        in_ready = frame_active_reg && !record_active_reg;
        write_valid = record_active_reg;
        write_slot_id = record_slot_id_reg;
        write_addr = record_addr_reg;
        write_awlen = 4'd0;
        write_data = {96'd0, data_reg};
        write_strb = {12'd0, keep_reg};
        write_last = last_reg;
        write_frame_end = frame_end_reg;
        write_protocol_error = protocol_error_reg;
    end

    /**
     * Intent: Hold one frame allocation and one normalized write record at a time.
     * FSM: `frame_active_reg` owns the slot; `record_active_reg` owns the output.
     * Invariant: Input is accepted only with an active slot, and address advancement
     *            stops before the first token outside the allocated capacity.
     * Latency: Allocation and record acceptance each become visible after one edge.
     * Hazard: A missing frame end or missing write acceptance retains the slot;
     *         timeout recovery belongs to the integrating frame manager.
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_active_reg      <= 1'b0;
            record_active_reg     <= 1'b0;
            frame_slot_id_reg     <= 1'b0;
            next_addr_reg         <= 28'd0;
            frame_capacity_reg    <= 32'd0;
            record_count_reg      <= 32'd0;
            capacity_exceeded_reg <= 1'b0;
            record_slot_id_reg    <= 1'b0;
            record_addr_reg       <= 28'd0;
            data_reg              <= 32'd0;
            keep_reg              <= 4'd0;
            last_reg              <= 1'b0;
            frame_end_reg         <= 1'b0;
            protocol_error_reg    <= 1'b0;
        end else begin
            if (frame_alloc_valid && frame_alloc_ready) begin
                frame_active_reg      <= 1'b1;
                frame_slot_id_reg     <= frame_alloc_slot_id;
                next_addr_reg         <= frame_alloc_base_addr;
                frame_capacity_reg    <= frame_alloc_record_capacity;
                record_count_reg      <= 32'd0;
                capacity_exceeded_reg <=
                    (frame_alloc_record_capacity == 32'd0);
            end

            if (in_valid && in_ready) begin
                record_active_reg  <= 1'b1;
                record_slot_id_reg <= frame_slot_id_reg;
                record_addr_reg    <= next_addr_reg;
                data_reg           <= in_data;
                keep_reg           <= in_keep;
                last_reg           <= in_last;
                frame_end_reg      <= in_frame_end;
                protocol_error_reg <= in_protocol_error |
                                      capacity_exceeded_reg;
            end

            if (record_active_reg && write_ready) begin
                record_active_reg <= 1'b0;
                if (frame_end_reg) begin
                    frame_active_reg      <= 1'b0;
                    record_count_reg      <= 32'd0;
                    capacity_exceeded_reg <= 1'b0;
                end else begin
                    record_count_reg <= record_count_reg + 32'd1;
                    if ((record_count_reg + 32'd1) <
                        frame_capacity_reg) begin
                        next_addr_reg <= next_addr_reg + ADDR_STEP;
                    end else begin
                        capacity_exceeded_reg <= 1'b1;
                    end
                end
            end
        end
    end
endmodule

`default_nettype wire
