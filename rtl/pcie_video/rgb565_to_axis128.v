module rgb565_to_axis128 (
    input              clk,
    input              rst_n,
    input              pixel_valid,
    input      [15:0]  pixel_data,
    input              frame_start,
    output reg         axis_valid,
    input              axis_ready,
    output reg [127:0] axis_data,
    output reg [3:0]   axis_keep,
    output reg         axis_last,
    output reg [7:0]   axis_user
);

reg [2:0] word_count;
reg [127:0] pack_data;
reg frame_active;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        word_count <= 3'd0;
        pack_data <= 128'd0;
        frame_active <= 1'b0;
        axis_valid <= 1'b0;
        axis_data <= 128'd0;
        axis_keep <= 4'hf;
        axis_last <= 1'b0;
        axis_user <= 8'd0;
    end else begin
        if (frame_start) begin
            word_count <= 3'd0;
            frame_active <= 1'b1;
        end

        if (axis_valid && axis_ready) begin
            axis_valid <= 1'b0;
            axis_last <= 1'b0;
        end

        if (pixel_valid && frame_active && (!axis_valid || axis_ready)) begin
            pack_data <= {pixel_data, pack_data[127:16]};
            if (word_count == 3'd7) begin
                axis_valid <= 1'b1;
                axis_data <= {pixel_data, pack_data[127:16]};
                axis_keep <= 4'hf;
                axis_last <= 1'b0;
                axis_user <= 8'h00;
                word_count <= 3'd0;
            end else begin
                word_count <= word_count + 1'b1;
            end
        end
    end
end

endmodule
