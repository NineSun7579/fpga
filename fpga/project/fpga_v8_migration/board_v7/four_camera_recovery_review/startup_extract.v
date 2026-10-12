module review_startup(input clk_50m,output camera_ctrl_rst_n_out,output cam_rst_n);
parameter CLK_FREQ=50000000;
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

wire rst_n=camera_ctrl_rst_n;
assign camera_ctrl_rst_n_out=camera_ctrl_rst_n;
reg [$clog2(CLK_FREQ/1000*7) : 0] power_on_cnt; // 18λ�㹻�� 250,000
reg                               i2c_start_en;

always @(posedge clk_50m or negedge rst_n) begin
    if (!rst_n) begin
        power_on_cnt  <= 18'd0;
        i2c_start_en  <= 1'b0; // ǿ�а�ס�ײ�� I2C ģ��
    end 
    else begin
        if (power_on_cnt < CLK_FREQ/1000*7) begin 
            power_on_cnt <= power_on_cnt + 1'b1;
        end 
        else begin
            // 5ms ���ˣ�ͬʱ���֣�
            i2c_start_en  <= 1'b1; // I2C ģ�����ѣ���ʼ���������Լ��� 20ms
        end
    end
end

assign cam_rst_n = i2c_start_en;
endmodule
