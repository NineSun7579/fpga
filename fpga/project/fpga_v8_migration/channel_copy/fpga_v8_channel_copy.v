// Isolated channel-group copy for [row, column, group, lane] uint8 streams.
// Each 128-bit word contains lanes 0..15 in bits [7:0]..[127:120].
// Source length comes only from the accepted command; s_last is diagnostic.
module fpga_v8_channel_copy (
    input wire clk,
    input wire rst_n,

    input wire cmd_valid,
    output wire cmd_ready,
    input wire [31:0] cmd_total_pixels,
    input wire [15:0] cmd_groups_per_pixel,
    input wire [15:0] cmd_first_group,
    input wire [15:0] cmd_group_count,
    output reg cmd_error,

    input wire s_valid,
    output wire s_ready,
    input wire [127:0] s_data,
    input wire s_last,

    output reg m_valid,
    input wire m_ready,
    output reg [127:0] m_data,
    output reg m_last,

    output reg busy,
    output reg done,
    output reg frame_error
);

    reg [31:0] pixels_remaining;
    reg [15:0] groups_per_pixel;
    reg [15:0] first_group;
    reg [16:0] end_group;
    reg [15:0] group_index;
    reg source_complete;
    reg output_complete;

    wire [16:0] command_end;
    wire command_good;
    wire selected;
    wire output_room;
    wire source_final;
    wire selected_final;
    wire input_fire;
    wire output_fire;
    wire source_finishing;
    wire output_finishing;

    assign command_end = {1'b0, cmd_first_group} +
                         {1'b0, cmd_group_count};
    assign command_good = (cmd_total_pixels != 32'd0) &&
                          (cmd_groups_per_pixel != 16'd0) &&
                          (cmd_group_count != 16'd0) &&
                          (command_end <= {1'b0, cmd_groups_per_pixel});

    // The done pulse is visible for a full cycle before another acceptance.
    assign cmd_ready = rst_n && !busy && !m_valid && !done;
    assign selected = (group_index >= first_group) &&
                      ({1'b0, group_index} < end_group);
    assign output_room = !m_valid || m_ready;
    // A skipped word never changes a pending selected output.
    assign s_ready = rst_n && busy && !source_complete &&
                     (!selected || output_room);
    assign input_fire = s_valid && s_ready;
    assign output_fire = m_valid && m_ready;
    assign source_final = (pixels_remaining == 32'd1) &&
                          (group_index == groups_per_pixel - 16'd1);
    assign selected_final = (pixels_remaining == 32'd1) &&
                            ({1'b0, group_index} == end_group - 17'd1);
    assign source_finishing = source_complete ||
                              (input_fire && source_final);
    assign output_finishing = output_complete ||
                              (output_fire && m_last);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pixels_remaining <= 32'd0;
            groups_per_pixel <= 16'd0;
            first_group <= 16'd0;
            end_group <= 17'd0;
            group_index <= 16'd0;
            source_complete <= 1'b0;
            output_complete <= 1'b0;
            cmd_error <= 1'b0;
            m_valid <= 1'b0;
            m_data <= 128'd0;
            m_last <= 1'b0;
            busy <= 1'b0;
            done <= 1'b0;
            frame_error <= 1'b0;
        end else begin
            cmd_error <= 1'b0;
            done <= 1'b0;

            if (output_fire) begin
                m_valid <= 1'b0;
                m_last <= 1'b0;
                if (m_last)
                    output_complete <= 1'b1;
            end

            if (cmd_valid && cmd_ready) begin
                if (command_good) begin
                    pixels_remaining <= cmd_total_pixels;
                    groups_per_pixel <= cmd_groups_per_pixel;
                    first_group <= cmd_first_group;
                    end_group <= command_end;
                    group_index <= 16'd0;
                    source_complete <= 1'b0;
                    output_complete <= 1'b0;
                    frame_error <= 1'b0;
                    busy <= 1'b1;
                end else begin
                    cmd_error <= 1'b1;
                end
            end

            if (input_fire) begin
                if (s_last != source_final)
                    frame_error <= 1'b1;

                if (selected) begin
                    m_data <= s_data;
                    m_last <= selected_final;
                    m_valid <= 1'b1;
                end

                if (source_final) begin
                    source_complete <= 1'b1;
                end else if (group_index == groups_per_pixel - 16'd1) begin
                    group_index <= 16'd0;
                    pixels_remaining <= pixels_remaining - 32'd1;
                end else begin
                    group_index <= group_index + 16'd1;
                end
            end

            // Remember output completion even if trailing skipped words
            // arrive later. Equally, remember source completion while the
            // final output is stalled. Neither path depends on s_last.
            if (busy && source_finishing && output_finishing) begin
                busy <= 1'b0;
                done <= 1'b1;
            end
        end
    end
endmodule
