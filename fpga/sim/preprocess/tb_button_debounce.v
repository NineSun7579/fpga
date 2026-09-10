`timescale 1ns/1ps
//============================================================================
// tb_button_debounce.v : 按键消抖单元仿真
//   STABLE_CYCLES=50: <50 拍毛刺被滤除, >=50 拍稳定电平被接受并打 toggle
//   覆盖: 正脉冲接受 / 负脉冲接受 / 短毛刺滤除(高/低两向) / toggle 单拍性
//============================================================================
module tb_button_debounce;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  btn_in = 1'b0;
    wire btn_level, btn_toggle, btn_pressed;

    button_debounce #(.STABLE_CYCLES(20'd50)) dut (
        .clk(clk), .rst_n(rst_n),
        .btn_in(btn_in),
        .btn_level(btn_level),
        .btn_toggle(btn_toggle),
        .btn_pressed(btn_pressed)
    );

    integer err = 0;
    integer toggle_cnt = 0;

    // toggle 计数 (应为每电平迁移恰好 1 次)
    always @(posedge clk) begin
        if (rst_n && btn_toggle)
            toggle_cnt = toggle_cnt + 1;
    end

    task press(input integer hold_cycles);
        begin
            btn_in = 1'b1;
            repeat (hold_cycles) @(posedge clk);
            btn_in = 1'b0;
            repeat (20) @(posedge clk);
        end
    endtask

    task glitch_high(input integer g);
        begin
            btn_in = 1'b1;
            repeat (g) @(posedge clk);
            btn_in = 1'b0;
            repeat (100) @(posedge clk);
        end
    endtask

    initial begin
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (10) @(posedge clk);

        // 1) 短毛刺 (10, 30 拍 < 50) 必须被滤除
        glitch_high(10);
        if (btn_level !== 1'b0) begin
            $display("[BTN][ERR] 10拍毛刺未被滤除"); err = err + 1;
        end
        glitch_high(30);
        if (btn_level !== 1'b0) begin
            $display("[BTN][ERR] 30拍毛刺未被滤除"); err = err + 1;
        end
        if (toggle_cnt != 0) begin
            $display("[BTN][ERR] 毛刺不应产生 toggle: %0d", toggle_cnt); err = err + 1;
        end

        // 2) 长按 (60 拍 >= 50) 必须被接受
        press(60);
        if (btn_level !== 1'b1) begin
            $display("[BTN][ERR] 60拍未接受"); err = err + 1;
        end
        if (toggle_cnt != 1) begin
            $display("[BTN][ERR] 接受应恰好1次toggle: %0d", toggle_cnt); err = err + 1;
        end

        // 3) 再短按一下 (电平已高, 60拍低) 释放
        btn_in = 1'b0;
        repeat (60) @(posedge clk);
        btn_in = 1'b1;
        repeat (20) @(posedge clk);
        btn_in = 1'b0;
        repeat (60) @(posedge clk);
        if (btn_level !== 1'b0) begin
            $display("[BTN][ERR] 释放未接受"); err = err + 1;
        end
        if (toggle_cnt != 2) begin
            $display("[BTN][ERR] 应累计2次toggle: %0d", toggle_cnt); err = err + 1;
        end

        if (err == 0)
            $display("[BTN] TB_PASS");
        else
            $display("[BTN] TB_FAIL  err=%0d", err);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("[BTN] TB_FAIL  超时");
        $finish;
    end

endmodule
