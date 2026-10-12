`timescale 1ns / 1ps
// tb_sccb_read_probe.v : self-checking testbench for sccb_read_probe.
//   Slave model responds ONLY when the device address matches `dev_id`.
//   Covers: correct address, wrong address, no slave, ACK error reporting,
//           and `start` arriving at different idle phases (regression for the
//           START-phase fix: the probe must hold ph=0 while idle).
module tb_sccb_read_probe;

    reg  clk = 0, rst_n = 0, start = 0;
    reg  [15:0] reg_addr = 16'h0000;
    reg  [7:0]  dev_id   = 8'h78;      // master device address
    reg         slave_present = 1;     // slave physically present?
    wire [7:0]  rdata;
    wire        rdata_valid, busy, ack_err, sda_low, scl;
    reg         sda_slave_low = 0;

    wire sda = sda_slave_low ? 1'b0 : (sda_low ? 1'b0 : 1'b1);

    always #20 clk = ~clk;   // 25MHz

    sccb_read_probe #(.CLK_HZ(25_000_000), .SCL_HZ(100_000)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .reg_addr(reg_addr), .dev_id(dev_id),
        .rdata(rdata), .rdata_valid(rdata_valid), .busy(busy), .ack_err(ack_err),
        .sda_in(sda), .sda_low(sda_low), .scl(scl)
    );

    // ---------------- slave model ----------------
    integer   biti = 0, bytei = 0;
    reg [7:0] sh = 0;
    reg [15:0] addr = 0;
    reg [7:0]  dout = 0;
    reg        read_phase = 0;
    localparam [7:0] SLAVE_ADDR = 8'h78;   // slave's own fixed address
    reg        addr_match = 0;

    function [7:0] regfile(input [15:0] a);
        case (a)
            16'h300A: regfile = 8'h56;
            16'h300B: regfile = 8'h40;
            16'h4300: regfile = 8'h60;
            default:  regfile = 8'h00;
        endcase
    endfunction

    always @(negedge sda) if (scl) begin
        biti = 0; bytei = 0; read_phase = 0; addr_match = 0; sda_slave_low = 1'b0;
    end

    reg ack_drive = 0;
    always @(negedge scl) begin
        if (read_phase) begin
            if (biti < 8) sda_slave_low <= ~dout[7-biti];
            else          sda_slave_low <= 1'b0;
            ack_drive <= 1'b0;
        end
        else if (biti == 8) begin
            // byte0 = device address (match it directly); later bytes use the latched match
            if (bytei == 0)
                sda_slave_low <= slave_present & ((sh == SLAVE_ADDR) || (sh == {SLAVE_ADDR[7:1],1'b1}));
            else
                sda_slave_low <= slave_present & addr_match;
            ack_drive <= 1'b1;
        end
        else if (ack_drive) begin
            sda_slave_low <= 1'b0;
            ack_drive     <= 1'b0;
        end
        else begin
            sda_slave_low <= 1'b0;
        end
    end

    always @(posedge scl) begin
        if (biti < 8) begin
            sh = {sh[6:0], sda};
            biti = biti + 1;
        end
        else begin
            biti = 0;
            if (bytei == 0) begin
                addr_match <= 1'b0;
                if (slave_present && (sh == SLAVE_ADDR)) begin
                    addr_match <= 1'b1; read_phase <= 1'b0;
                    $display("[%0t] SLAVE dev=0x%02h (W)", $time, sh);
                end
                else if (slave_present && (sh == {SLAVE_ADDR[7:1],1'b1})) begin
                    addr_match <= 1'b1; read_phase <= 1'b1; dout <= regfile(addr);
                    $display("[%0t] SLAVE dev=0x%02h (R) addr=%04h -> %02h", $time, sh, addr, regfile(addr));
                end
                else begin
                    $display("[%0t] SLAVE ignores dev=0x%02h", $time, sh);
                end
                bytei = 1;
            end
            else if (!read_phase && bytei == 1) begin addr[15:8] = sh; bytei = 2; end
            else if (!read_phase && bytei == 2) begin addr[7:0]  = sh; bytei = 3; end
        end
    end

    // ---------------- protocol monitor (P1-2) ----------------
    //   A legal SCCB/I2C transaction: START, 4 bytes with ACK, RESTART, dev+R,
    //   read byte with NAK, STOP  => 45 SCL rising edges and 2 STARTs.
    //   SDA may only change while SCL is low, except at START/STOP.
    integer p_scl = 0, p_start = 0, p_err = 0;
    reg     in_trans = 0;
    reg     mon_en = 0;    // only assert during known-good transactions
    always @(posedge scl) if (in_trans && mon_en) p_scl = p_scl + 1;
    always @(negedge sda) if (scl && mon_en) begin
        if (!in_trans) begin in_trans = 1; p_scl = 0; p_start = 1; end
        else p_start = p_start + 1;
    end
    always @(posedge sda) if (scl && in_trans && mon_en) begin
        in_trans = 0;
        if (p_scl != 45) begin
            $display("PROTO ERROR [%0t]: %0d SCL edges in transaction (expect 45)", $time, p_scl);
            p_err = p_err + 1;
        end
        if (p_start != 2) begin
            $display("PROTO ERROR [%0t]: %0d STARTs (expect 2)", $time, p_start);
            p_err = p_err + 1;
        end
    end

    // ---------------- stimulus ----------------
    integer errors = 0;
    // `pre_clk`: idle clocks before asserting start (varies the idle phase)
    task do_read(input [15:0] a, input [7:0] exp, input exp_ackerr, input [8*12:1] tag, input integer pre_clk);
        reg [7:0] got;
        reg       ae;
        begin
            repeat (pre_clk) @(posedge clk);
            reg_addr = a; start = 1;
            @(posedge rdata_valid);
            #1;
            got = rdata; ae = ack_err;
            $display("[%0t] %0s addr=%04h got=%02h exp=%02h ack_err=%b(exp %b)",
                     $time, tag, a, got, exp, ae, exp_ackerr);
            if (ae !== exp_ackerr) begin
                $display("  ERROR: ack_err mismatch");
                errors = errors + 1;
            end
            if (exp_ackerr === 1'b0 && got !== exp) begin
                $display("  ERROR: data mismatch");
                errors = errors + 1;
            end
            start = 0;
            @(negedge busy);
            repeat (5) @(posedge clk);
        end
    endtask

    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1;
        repeat (5) @(posedge clk);

        // 1) correct address, expected data + no ACK error
        mon_en = 1;
        do_read(16'h300A, 8'h56, 1'b0, "ok-300A", 0);
        do_read(16'h300B, 8'h40, 1'b0, "ok-300B", 0);
        do_read(16'h4300, 8'h60, 1'b0, "ok-4300", 0);

        // 2) start arriving at different idle phases (regression for START-phase fix)
        do_read(16'h300A, 8'h56, 1'b0, "phase1", 1);
        do_read(16'h300A, 8'h56, 1'b0, "phase2", 37);
        do_read(16'h300A, 8'h56, 1'b0, "phase3", 137);
        do_read(16'h300A, 8'h56, 1'b0, "phase4", 271);

        mon_en = 0;

        // 3) wrong address: slave present but not addressed -> expect ack_err
        dev_id = 8'h7A;
        do_read(16'h300A, 8'h00, 1'b1, "badaddr", 0);
        dev_id = 8'h78;

        // 4) no slave at all -> expect ack_err
        slave_present = 0;
        do_read(16'h300A, 8'h00, 1'b1, "noslave", 0);
        slave_present = 1;

        errors = errors + p_err;
        if (errors == 0) $display("=== TEST PASS ===");
        else             $display("=== TEST FAIL errors=%0d ===", errors);
        $finish;
    end

    initial begin
        #50_000_000;
        $display("=== TIMEOUT ===");
        $finish;
    end

endmodule
