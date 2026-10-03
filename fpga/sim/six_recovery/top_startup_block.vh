reg [15:0] camera_startup_count = 16'd0;
reg camera_ctrl_rst_n = 1'b0;
always @(posedge clk_50m) begin
    if (!camera_ctrl_rst_n) begin
        if (&camera_startup_count)
            camera_ctrl_rst_n <= 1'b1;
        else
            camera_startup_count <= camera_startup_count + 1'b1;
    end
end
