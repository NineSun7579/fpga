`timescale 1ns/1ns

module tb_rgb565_to_axis128;

reg clk;
reg rst_n;
reg pixel_valid;
reg [15:0] pixel_data;
reg frame_start;
wire axis_valid;
wire axis_ready;
wire [127:0] axis_data;
wire [3:0] axis_keep;
wire axis_last;
wire [7:0] axis_user;
reg [10:0] rd_addr;
wire [127:0] rd_data;
integer word_count;

rgb565_to_axis128 u_packer (
    .clk(clk),
    .rst_n(rst_n),
    .pixel_valid(pixel_valid),
    .pixel_data(pixel_data),
    .frame_start(frame_start),
    .axis_valid(axis_valid),
    .axis_ready(axis_ready),
    .axis_data(axis_data),
    .axis_keep(axis_keep),
    .axis_last(axis_last),
    .axis_user(axis_user)
);

axis128_bar2_ram u_ram (
    .wr_clk(clk),
    .wr_rst_n(rst_n),
    .axis_valid(axis_valid),
    .axis_ready(axis_ready),
    .axis_data(axis_data),
    .rd_clk(clk),
    .rd_addr(rd_addr),
    .rd_data(rd_data)
);

initial clk = 1'b0;
always #5 clk = ~clk;

initial begin
    rst_n = 1'b0;
    pixel_valid = 1'b0;
    pixel_data = 16'd0;
    frame_start = 1'b0;
    rd_addr = 11'd0;
    word_count = 0;
    #25 rst_n = 1'b1;
    @(posedge clk);
    frame_start <= 1'b1;
    @(posedge clk);
    frame_start <= 1'b0;
    repeat (16) begin
        @(posedge clk);
        pixel_valid <= 1'b1;
        pixel_data <= word_count;
        word_count = word_count + 1;
    end
    @(posedge clk);
    pixel_valid <= 1'b0;
    repeat (4) @(posedge clk);
    rd_addr <= 11'd0;
    @(posedge clk);
    @(posedge clk);
    if (rd_data !== {16'd7, 16'd6, 16'd5, 16'd4, 16'd3, 16'd2, 16'd1, 16'd0})
        $fatal(1, "BAR2 word 0 mismatch: %h", rd_data);
    rd_addr <= 11'd1;
    @(posedge clk);
    @(posedge clk);
    if (rd_data !== {16'd15, 16'd14, 16'd13, 16'd12, 16'd11, 16'd10, 16'd9, 16'd8})
        $fatal(1, "BAR2 word 1 mismatch: %h", rd_data);
    $display("PASS: RGB565 to AXI128 and BAR2 frame buffer verified");
    $finish;
end

endmodule
