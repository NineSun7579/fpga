
`timescale 1ns/1ps
module tb_pt_fsm;
    reg dri_clk = 0, rst_n = 0;
    always #5 dri_clk = ~dri_clk;

    reg         cam_init_done = 0;
    reg         cfg_exec = 0, cfg_rh_wl = 0;
    reg  [23:0] cfg_data = 0;
    reg         i2c_done = 0, i2c_ack = 0;
    reg  [7:0]  i2c_data_r = 0;
    reg         pt_req_toggle = 0, pt_rw = 0;
    reg  [15:0] pt_addr = 0;
    reg  [7:0]  pt_wdata = 0;
    wire [7:0]  pt_rdata;
    wire        pt_ack, pt_done_toggle;
    wire        i2c_exec, i2c_rh_wl;
    wire [23:0] i2c_data;

    pt_fsm_under_test dut(.dri_clk(dri_clk), .rst_n(rst_n),
        .cam_init_done(cam_init_done), .cfg_exec(cfg_exec), .cfg_data(cfg_data),
        .cfg_rh_wl(cfg_rh_wl), .i2c_done(i2c_done), .i2c_ack(i2c_ack),
        .i2c_data_r(i2c_data_r), .pt_req_toggle(pt_req_toggle), .pt_rw(pt_rw),
        .pt_addr(pt_addr), .pt_wdata(pt_wdata), .pt_rdata(pt_rdata),
        .pt_ack(pt_ack), .pt_done_toggle(pt_done_toggle),
        .i2c_exec(i2c_exec), .i2c_data(i2c_data), .i2c_rh_wl(i2c_rh_wl));

    // fake I2C master: answer each exec after a few cycles
    integer mst_state = 0, mst_timer = 0;
    reg [23:0] mst_cap = 0;
    reg        mst_rw = 0;
    reg [7:0]  next_rd = 8'h56;
    reg [15:0] nack_addr = 16'hFFFF;

    integer exec_count = 0;
    reg [23:0] last_exec_data = 0;
    reg        last_exec_rw = 0;

    always @(posedge dri_clk) begin
        if (i2c_exec) begin
            exec_count      <= exec_count + 1;
            last_exec_data  <= i2c_data;
            last_exec_rw    <= i2c_rh_wl;
        end
    end

    always @(posedge dri_clk) begin
        i2c_done <= 1'b0;
        case (mst_state)
          0: if (i2c_exec) begin
                 mst_cap   <= i2c_data;
                 mst_rw    <= i2c_rh_wl;
                 mst_timer <= 3;
                 mst_state <= 1;
             end
          1: if (mst_timer == 0) begin
                 i2c_ack    <= (mst_cap[23:8] == nack_addr);
                 i2c_data_r <= mst_rw ? next_rd : 8'h00;
                 i2c_done   <= 1'b1;
                 mst_state  <= 2;
             end else mst_timer <= mst_timer - 1;
          2: mst_state <= 0;
        endcase
    end

    integer errors = 0;
    reg [31:0] prev_done;
    task check(input [255:0] name, input [31:0] got, input [31:0] exp);
        begin
            if (got !== exp) begin $display("FAIL %0s: got 0x%08X exp 0x%08X", name, got, exp); errors=errors+1; end
            else $display("PASS %0s = 0x%08X", name, got);
        end
    endtask

    task wait_done_change;
        begin
            prev_done = pt_done_toggle;
            while (pt_done_toggle === prev_done) @(posedge dri_clk);
            repeat (2) @(posedge dri_clk);
        end
    endtask

    task send_cmd(input rw, input [15:0] a, input [7:0] d);
        begin
            pt_rw = rw; pt_addr = a; pt_wdata = d;
            @(posedge dri_clk);
            pt_req_toggle = ~pt_req_toggle;
        end
    endtask

    initial begin
        repeat (4) @(posedge dri_clk);
        rst_n = 1;
        repeat (2) @(posedge dri_clk);

        // --- before init: command must be held, no exec ---
        cfg_exec = 1; @(posedge dri_clk); cfg_exec = 0;
        repeat (8) @(posedge dri_clk);          // cfg transaction answered
        $display("exec after cfg = %0d", exec_count);
        send_cmd(1'b1, 16'h300A, 8'h00);       // early read while init not done
        repeat (8) @(posedge dri_clk);
        check("no exec before init_done", exec_count, 1);

        // --- init done: held command now runs ---
        cam_init_done = 1;
        wait_done_change;
        check("exec count after early cmd", exec_count, 2);
        check("read: rh_wl", last_exec_rw, 1);
        check("read: addr", last_exec_data[23:8], 16'h300A);
        check("read: data", pt_rdata, 8'h56);
        check("read: ack", pt_ack, 0);

        // --- write command (flash on) ---
        next_rd = 8'h00;
        send_cmd(1'b0, 16'h3019, 8'h02);
        wait_done_change;
        check("write: exec count", exec_count, 3);
        check("write: rh_wl", last_exec_rw, 0);
        check("write: addr", last_exec_data[23:8], 16'h3019);
        check("write: wdata", last_exec_data[7:0], 8'h02);

        // --- NACK reporting ---
        send_cmd(1'b1, 16'hFFFF, 8'h00);
        wait_done_change;
        check("nack: exec count", exec_count, 4);
        check("nack: ack", pt_ack, 1);

        // --- idle: no spurious exec ---
        repeat (20) @(posedge dri_clk);
        check("no spurious exec", exec_count, 4);

        if (errors == 0) $display("PASS ov5640 PT FSM");
        else             $display("FAIL ov5640 PT FSM (%0d)", errors);
        $finish;
    end

    initial begin #100000; $display("FAIL timeout"); $finish; end
endmodule
