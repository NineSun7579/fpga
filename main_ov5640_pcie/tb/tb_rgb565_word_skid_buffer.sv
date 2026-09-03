`timescale 1ns/1ps
`default_nettype none

/**
 * @file tb_rgb565_word_skid_buffer.sv
 * @brief 验证 camera-side word 缓冲的顺序、溢出中止和帧边界恢复。
 */
module tb_rgb565_word_skid_buffer;
    logic        rst_n = 1'b0;
    logic        clk = 1'b0;
    logic        in_valid = 1'b0;
    logic [127:0] in_data = 128'h0;
    logic [15:0] in_keep = 16'h0;
    logic        in_frame_start = 1'b0;
    logic        in_line_start = 1'b0;
    logic        in_line_end = 1'b0;
    logic        in_frame_end = 1'b0;
    logic        in_protocol_error = 1'b0;
    logic        in_ready;
    logic        out_valid;
    logic        out_ready = 1'b0;
    logic [127:0] out_data;
    logic [15:0] out_keep;
    logic        out_frame_start;
    logic        out_line_start;
    logic        out_line_end;
    logic        out_frame_end;
    logic        out_protocol_error;
    logic        overflow;
    integer received = 0;

    rgb565_word_skid_buffer dut (.*);

    always #5ns clk = ~clk;
    initial begin
        #2us;
        $fatal(1, "word skid buffer timeout");
    end

    task automatic send_word(input logic [127:0] value, input logic [15:0] keep,
                             input logic frame_start, input logic frame_end);
        begin
            @(negedge clk);
            in_valid = 1'b1;
            in_data = value;
            in_keep = keep;
            in_frame_start = frame_start;
            in_frame_end = frame_end;
            @(posedge clk);
            #1ns;
            in_valid = 1'b0;
            in_frame_start = 1'b0;
            in_frame_end = 1'b0;
        end
    endtask

    task automatic reset_dut;
        begin
            in_valid = 1'b0;
            in_frame_start = 1'b0;
            in_frame_end = 1'b0;
            out_ready = 1'b0;
            rst_n = 1'b0;
            repeat (2) @(posedge clk);
            rst_n = 1'b1;
        end
    endtask

    task automatic consume_word(input logic [127:0] value, input logic [15:0] keep,
                                input logic frame_start, input logic frame_end,
                                input logic protocol_error);
        begin
            out_ready = 1'b1;
            wait (out_valid);
            @(negedge clk);
            if (out_data !== value || out_keep !== keep ||
                out_frame_start !== frame_start || out_frame_end !== frame_end ||
                out_protocol_error !== protocol_error || !out_valid || !out_ready)
                $fatal(1, "output word mismatch: data=%h keep=%h fs=%b fe=%b err=%b",
                       out_data, out_keep, out_frame_start, out_frame_end,
                       out_protocol_error);
            @(posedge clk);
            #1ns;
        end
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        // 下游暂停时，当前帧的两个输入 word 必须按顺序保存。
        send_word(128'h1000, 16'hffff, 1'b1, 1'b0);
        send_word(128'h2000, 16'h000f, 1'b0, 1'b0);
        if (!in_ready)
            $display("INFO: word skid buffer is full after two words");

        // 第三个 word 触发溢出，后续原帧内容必须进入有意丢弃状态。
        send_word(128'h3000, 16'h0003, 1'b0, 1'b0);
        if (!overflow || in_ready)
            $fatal(1, "word skid drop-mode contract mismatch: overflow=%b ready=%b",
                   overflow, in_ready);
        send_word(128'h4000, 16'h0001, 1'b0, 1'b1);

        // 中止记录尚未排队时到达的新帧必须整帧跳过，不能抢在中止记录前输出。
        send_word(128'h4500, 16'h000f, 1'b1, 1'b1);

        out_ready = 1'b1;
        wait (out_valid);
        @(negedge clk);
        if (out_data !== 128'h1000 || out_keep !== 16'hffff ||
            !out_frame_start || out_frame_end || !out_valid || !out_ready)
            $fatal(1, "first buffered word mismatch: data=%h keep=%h fs=%b fe=%b",
                   out_data, out_keep, out_frame_start, out_frame_end);
        @(posedge clk);

        wait (out_valid);
        @(negedge clk);
        if (out_data !== 128'h2000 || out_keep !== 16'h000f ||
            out_frame_start || out_frame_end || out_protocol_error ||
            !out_valid || !out_ready)
            $fatal(1, "second buffered word mismatch: data=%h keep=%h fs=%b fe=%b",
                   out_data, out_keep, out_frame_start, out_frame_end);
        @(posedge clk);

        // 已保存前缀之后必须恰好输出一个空载错误帧尾，使下游作废该帧。
        wait (out_valid);
        @(negedge clk);
        if (out_data !== 128'h0 || out_keep !== 16'h0 || out_frame_start ||
            !out_frame_end || !out_protocol_error || !out_valid || !out_ready)
            $fatal(1, "synthetic frame abort mismatch: data=%h keep=%h fs=%b fe=%b err=%b",
                   out_data, out_keep, out_frame_start, out_frame_end,
                   out_protocol_error);
        @(posedge clk);

        repeat (2) @(posedge clk);
        if (out_valid)
            $fatal(1, "word skid buffer did not drain");

        // 只有新的 frame_start 才能结束丢帧状态并恢复正常输出。
        send_word(128'h5000, 16'h000f, 1'b1, 1'b1);
        wait (out_valid);
        @(negedge clk);
        if (out_data !== 128'h5000 || out_keep !== 16'h000f ||
            !out_frame_start || !out_frame_end || out_protocol_error)
            $fatal(1, "next-frame recovery mismatch");
        @(posedge clk);
        repeat (2) @(posedge clk);
        if (out_valid || !overflow)
            $fatal(1, "word skid recovery or sticky overflow mismatch");
        $display("INFO: overflow abort marker and next-frame recovery verified");

        // 满队列同拍出队和入队必须替换尾槽，不得误报 overflow 或改变 FIFO 顺序。
        reset_dut();
        send_word(128'h6100, 16'hffff, 1'b1, 1'b0);
        send_word(128'h6200, 16'h00ff, 1'b0, 1'b0);
        @(negedge clk);
        out_ready = 1'b1;
        in_valid = 1'b1;
        in_data = 128'h6300;
        in_keep = 16'h000f;
        in_frame_end = 1'b1;
        if (out_data !== 128'h6100 || !out_frame_start)
            $fatal(1, "full queue replacement lost the head word");
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        in_frame_end = 1'b0;
        consume_word(128'h6200, 16'h00ff, 1'b0, 1'b0, 1'b0);
        consume_word(128'h6300, 16'h000f, 1'b0, 1'b1, 1'b0);
        if (out_valid || overflow)
            $fatal(1, "full queue replacement changed queue depth or overflow");

        // 丢弃侧 frame_end 与 abort 入队同拍时，原帧结束事实和唯一中止都必须保留。
        reset_dut();
        send_word(128'h7100, 16'hffff, 1'b1, 1'b0);
        send_word(128'h7200, 16'hffff, 1'b0, 1'b0);
        send_word(128'h7300, 16'hffff, 1'b0, 1'b0);
        @(negedge clk);
        out_ready = 1'b1;
        in_valid = 1'b1;
        in_data = 128'h7400;
        in_keep = 16'h000f;
        in_frame_end = 1'b1;
        if (out_data !== 128'h7100 || in_ready)
            $fatal(1, "abort enqueue collision precondition mismatch");
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        in_frame_end = 1'b0;
        consume_word(128'h7200, 16'hffff, 1'b0, 1'b0, 1'b0);
        consume_word(128'h0, 16'h0, 1'b0, 1'b1, 1'b1);
        send_word(128'h7500, 16'h000f, 1'b1, 1'b1);
        consume_word(128'h7500, 16'h000f, 1'b1, 1'b1, 1'b0);

        // 第一帧 abort 尚未排出时，下一帧再次溢出仍必须按帧各输出一个 abort。
        reset_dut();
        send_word(128'h8100, 16'hffff, 1'b1, 1'b0);
        send_word(128'h8200, 16'hffff, 1'b0, 1'b0);
        send_word(128'h8300, 16'hffff, 1'b0, 1'b0);
        send_word(128'h8400, 16'h000f, 1'b0, 1'b1);
        consume_word(128'h8100, 16'hffff, 1'b1, 1'b0, 1'b0);

        // pop 旧前缀的同一拍接收第二帧帧首，队列变为 abort1、frame2_start。
        @(negedge clk);
        in_valid = 1'b1;
        in_data = 128'h8500;
        in_keep = 16'hffff;
        in_frame_start = 1'b1;
        #1ns;
        if (out_data !== 128'h8200 || !in_ready)
            $fatal(1, "second frame recovery enqueue mismatch");
        @(posedge clk);
        #1ns;
        in_valid = 1'b0;
        in_frame_start = 1'b0;
        out_ready = 1'b0;

        send_word(128'h8600, 16'hffff, 1'b0, 1'b0);
        send_word(128'h8700, 16'h000f, 1'b0, 1'b1);
        consume_word(128'h0, 16'h0, 1'b0, 1'b1, 1'b1);
        consume_word(128'h8500, 16'hffff, 1'b1, 1'b0, 1'b0);
        consume_word(128'h0, 16'h0, 1'b0, 1'b1, 1'b1);
        if (out_valid || !overflow)
            $fatal(1, "consecutive damaged-frame abort ordering mismatch");

        // 异步复位必须清除未排队 abort、旧 payload 和 sticky overflow。
        reset_dut();
        send_word(128'h9100, 16'hffff, 1'b1, 1'b0);
        send_word(128'h9200, 16'hffff, 1'b0, 1'b0);
        send_word(128'h9300, 16'hffff, 1'b0, 1'b0);
        rst_n = 1'b0;
        #1ns;
        if (out_valid || overflow)
            $fatal(1, "asynchronous reset leaked queued state");
        repeat (2) @(posedge clk);
        rst_n = 1'b1;
        #1ns;
        if (!in_ready || out_valid || overflow)
            $fatal(1, "reset recovery contract mismatch");

        $display("INFO: simultaneous replacement, abort collision, repeated abort, and reset verified");
        $display("TEST PASS");
        $finish;
    end
endmodule

`default_nettype wire
