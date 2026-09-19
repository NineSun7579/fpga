`timescale 1ns/1ps
module tb_ov5640_i2c;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #20 clk = ~clk; // 25 MHz board clock

    wire sda;
    wire scl;
    wire [7:0] data_r;
    wire i2c_done, i2c_ack, dri_clk;
    wire i2c_exec, i2c_rh_wl;
    wire [23:0] i2c_data;
    wire init_done;

    // Testbench SCCB slave: acknowledge every address/data byte and return 0
    // for read data. This checks the actual start/stop, bit and ACK timing.
    reg slave_drive;
    reg slave_sda;
    assign sda = slave_drive ? slave_sda : 1'bz;

    i2c_dri #(.SLAVE_ADDR(7'h3c), .CLK_FREQ(25_000_000), .I2C_FREQ(250_000)) u_dri (
        .clk(clk), .rst_n(rst_n), .i2c_exec(i2c_exec), .bit_ctrl(1'b1),
        .i2c_rh_wl(i2c_rh_wl), .i2c_addr(i2c_data[23:8]),
        .i2c_data_w(i2c_data[7:0]), .i2c_data_r(data_r),
        .i2c_done(i2c_done), .i2c_ack(i2c_ack), .scl(scl), .sda(sda),
        .dri_clk(dri_clk)
    );

    ov5640_i2c_rgb565_cfg #(.I2C_FREQ(250_000)) u_cfg (
        .clk(dri_clk), .rst_n(rst_n), .i2c_data_r(data_r),
        .i2c_done(i2c_done), .cmos_h_pixel(13'd1280),
        .cmos_v_pixel(13'd720), .total_h_pixel(13'd1892),
        .total_v_pixel(13'd740), .i2c_exec(i2c_exec),
        .i2c_data(i2c_data), .i2c_rh_wl(i2c_rh_wl), .init_done(init_done)
    );

    integer scl_edges, done_count, nack_count;
    integer tx_log_count;
    reg [23:0] tx_log [0:6999];
    reg scl_d;
    always @(posedge clk) begin
        scl_d <= scl;
        if (!scl_d && scl) scl_edges <= scl_edges + 1;
        if (i2c_done) begin
            done_count <= done_count + 1;
            if (i2c_ack) nack_count <= nack_count + 1;
            if (tx_log_count < 7000) begin
                tx_log[tx_log_count] <= i2c_data;
                tx_log_count <= tx_log_count + 1;
            end
        end
    end

    // Open-drain ACK model. The master samples ACK on the 9th rising edge of
    // each byte; hold SDA low during all ACK slots. Drive zero on read bits.
    integer bit_count;
    always @(negedge scl or negedge rst_n) begin
        if (!rst_n) begin
            bit_count <= 0;
            slave_drive <= 1'b0;
            slave_sda <= 1'b1;
        end else begin
            if (bit_count == 8 || bit_count == 17 || bit_count == 26 || bit_count == 35 ||
                bit_count == 44 || bit_count == 53 || bit_count == 62 || bit_count == 71) begin
                slave_drive <= 1'b1;
                slave_sda <= 1'b0;
            end else begin
                slave_drive <= 1'b0;
                slave_sda <= 1'b1;
            end
            bit_count <= bit_count + 1;
        end
    end

    always @(posedge scl) begin
        if (rst_n && (bit_count > 0)) begin
            // Release ACK drive after the ACK rising edge; count continues
            // through the transaction and resets on the next STOP/START.
            if (bit_count == 9 || bit_count == 18 || bit_count == 27 || bit_count == 36 ||
                bit_count == 45 || bit_count == 54 || bit_count == 63 || bit_count == 72)
                slave_drive <= 1'b0;
        end
    end

    task check_reg;
        input [15:0] addr;
        input [7:0] value;
        integer k;
        reg found;
        begin
            found = 1'b0;
            for (k = 0; k < 7000; k = k + 1)
                if (k < tx_log_count && tx_log[k][23:8] == addr && tx_log[k][7:0] == value)
                    found = 1'b1;
            if (!found) begin
                $display("I2C_MISSING addr=%h value=%h", addr, value);
                $fatal(1, "required register write missing");
            end
        end
    endtask

    initial begin
        scl_edges = 0; done_count = 0; nack_count = 0; tx_log_count = 0; scl_d = 0; bit_count = 0;
        #1000;
        rst_n = 1'b1;
        wait(init_done);
        #1000;
        $display("I2C_RESULT init_done=%0d done=%0d nack=%0d scl_edges=%0d tx_log=%0d last_addr=%h last_data=%h",
                 init_done, done_count, nack_count, scl_edges, tx_log_count, i2c_data[23:8], i2c_data[7:0]);
        if (!init_done || nack_count != 0 || done_count < 250 || tx_log_count < 250 || scl_edges < 9000)
            $fatal(1, "I2C configuration failed");
        check_reg(16'h3035, 8'h21);
        check_reg(16'h3036, 8'h69);
        check_reg(16'h4300, 8'h60);
        check_reg(16'h3820, 8'h47);
        check_reg(16'h3821, 8'h00);
        check_reg(16'h3808, 8'h05);
        check_reg(16'h3809, 8'h00);
        check_reg(16'h380a, 8'h02);
        check_reg(16'h380b, 8'hd0);
        check_reg(16'h380c, 8'h07);
        check_reg(16'h380d, 8'h64);
        check_reg(16'h380e, 8'h02);
        check_reg(16'h380f, 8'he4);
        check_reg(16'h460b, 8'h37);
        check_reg(16'h4837, 8'h16);
        check_reg(16'h3824, 8'h04);
        check_reg(16'h300e, 8'h58);
        check_reg(16'h302e, 8'h00);
        check_reg(16'h3034, 8'h1a);
        check_reg(16'h3002, 8'h1c);
        check_reg(16'h3006, 8'hc3);
        $display("I2C_CHECK key registers present");
        $finish;
    end

    initial begin
        #100_000_000;
        $fatal(1, "I2C simulation timeout");
    end
endmodule
