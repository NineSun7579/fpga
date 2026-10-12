`timescale 1ns/1ps
module tb_fpga_v8_ddr_write_arbiter;
    parameter integer CASE_ID = 0;
    parameter integer SEED = 12345;
    localparam integer M = 7;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg [M*4-1:0] m_awid;
    reg [M*32-1:0] m_awaddr;
    reg [M*8-1:0] m_awlen;
    reg [M*3-1:0] m_awsize, m_awprot;
    reg [M*2-1:0] m_awburst;
    reg [M-1:0] m_awlock, m_awvalid, m_wlast, m_wvalid, m_bready;
    reg [M*4-1:0] m_awcache, m_awqos, m_awregion;
    reg [M*128-1:0] m_wdata;
    reg [M*16-1:0] m_wstrb;
    wire [M-1:0] m_awready, m_wready, m_bvalid;
    wire [M*4-1:0] m_bid;
    wire [M*2-1:0] m_bresp;
    wire [3:0] s_awid, s_awcache, s_awqos, s_awregion;
    wire [31:0] s_awaddr;
    wire [7:0] s_awlen;
    wire [2:0] s_awsize, s_awprot;
    wire [1:0] s_awburst;
    wire s_awlock, s_awvalid, s_wlast, s_wvalid, s_bready;
    reg s_awready, s_wready, s_bvalid;
    wire [127:0] s_wdata;
    wire [15:0] s_wstrb;
    reg [3:0] s_bid;
    reg [1:0] s_bresp;
    wire busy, error;
    wire [2:0] owner;
    wire [4:0] error_flags;
    fpga_v8_ddr_write_arbiter dut (.*);

    // All monitor state is independent of the DUT internals. Requests are
    // observed on selection; grants are checked against a separate RR model.
    integer model_state, model_owner, model_rr, model_beat, model_length;
    integer seq [0:M-1], aw_done [0:M-1], next_beat [0:M-1], target [0:M-1];
    integer age_aw, age_w, age_b, mode, cycles = 0;
    integer aw_count = 0, w_count = 0, b_count = 0;
    integer aw_stalls = 0, w_stalls = 0, b_stalls = 0;
    integer pre_aw_w = 0, source_bubbles = 0, late_arrivals = 0;
    integer fault_changes = 0, reset_checks = 0;
    reg [4:0] expected_flags;
    reg [64:0] snapshot;
    reg [64:0] previous_aw [0:M-1];
    reg [144:0] previous_w [0:M-1];
    reg [M-1:0] aw_held, w_held;
    reg slave_aw_held, slave_w_held, slave_b_held;
    reg [64:0] previous_slave_aw;
    reg [144:0] previous_slave_w;
    reg [5:0] previous_slave_b;
    integer trace;
    string trace_path;
    reg [31:0] rng;

    function automatic [31:0] random_word;
        reg [31:0] x;
        begin
            x = rng;
            x = x ^ (x << 13);
            x = x ^ (x >> 17);
            x = x ^ (x << 5);
            rng = x;
            random_word = x;
        end
    endfunction
    function automatic integer length_for(input integer master, txn);
        begin
            if (mode == 2 || mode == 3) length_for = 16;
            else if (txn == 31) length_for = 256;
            else case (txn % 3)
                0: length_for = 1;
                1: length_for = 2;
                default: length_for = 16;
            endcase
        end
    endfunction
    function automatic [3:0] id_for(input integer master, txn);
        id_for = (txn < 16) ? 4'd9 : master + 1;
    endfunction
    function automatic [127:0] data_for(input integer master, txn, beat);
        integer lane;
        begin
            for (lane = 0; lane < 16; lane = lane + 1)
                data_for[lane*8 +: 8] =
                    (master*37 + txn*19 + beat*11 + lane*7) ^ (8'ha5 + lane);
        end
    endfunction
    function automatic [15:0] strb_for(input integer master, txn, beat);
        begin
            if ((master + txn + beat) % 4 == 0)
                strb_for = 16'hffff;
            else
                strb_for = (16'hf3c5 ^ (master*257 + txn*17 + beat*13));
        end
    endfunction
    function automatic last_for(input integer master, txn, beat);
        begin
            last_for = (beat == length_for(master, txn)-1);
            if (mode == 2 && (master == 2 || master == 5) && beat == 0)
                last_for = 1;
            if (mode == 2 && (master == 3 || master == 5) &&
                beat == length_for(master, txn)-1)
                last_for = 0;
        end
    endfunction
    function automatic [64:0] upstream_aw(input integer master);
        upstream_aw = {m_awid[master*4 +: 4], m_awaddr[master*32 +: 32],
            m_awlen[master*8 +: 8], m_awsize[master*3 +: 3],
            m_awburst[master*2 +: 2], m_awlock[master],
            m_awcache[master*4 +: 4], m_awprot[master*3 +: 3],
            m_awqos[master*4 +: 4], m_awregion[master*4 +: 4]};
    endfunction
    wire [64:0] slave_aw = {s_awid, s_awaddr, s_awlen, s_awsize,
        s_awburst, s_awlock, s_awcache, s_awprot, s_awqos, s_awregion};
    task automatic descriptor(input integer master, txn);
        integer length;
        begin
            length = length_for(master, txn);
            m_awid[master*4 +: 4] = id_for(master, txn);
            m_awaddr[master*32 +: 32] = 32'h00100000 + master*32'h00100000 + txn*8192;
            m_awlen[master*8 +: 8] = length-1;
            m_awsize[master*3 +: 3] = 4;
            m_awburst[master*2 +: 2] =
                (length != 1 && length != 256 && (master+txn)%2) ? 2 : 1;
            m_awlock[master] = (master + txn) % 2;
            m_awcache[master*4 +: 4] = master + txn;
            m_awprot[master*3 +: 3] = master ^ txn;
            m_awqos[master*4 +: 4] = master*3 + txn;
            m_awregion[master*4 +: 4] = master*5 + txn;
        end
    endtask
    task automatic fail(input string message);
        begin
            $display("FAIL cycle=%0d case=%0d state=%0d owner=%0d: %s",
                cycles, CASE_ID, model_state, model_owner, message);
            $fatal(1, "%s", message);
        end
    endtask

    integer i, scan, candidate, chosen;
    always @(posedge clk) begin
        cycles = cycles + 1;
        if (!rst_n) begin
            model_state = 0;
            model_owner = 0;
            model_rr = 0;
            model_beat = 0;
            model_length = 0;
            age_aw = 0; age_w = 0; age_b = 0;
            expected_flags = 0;
            aw_held = 0; w_held = 0;
            slave_aw_held = 0; slave_w_held = 0; slave_b_held = 0;
            for (i = 0; i < M; i = i + 1) begin
                seq[i] = 0; aw_done[i] = 0; next_beat[i] = 0;
            end
            if ({s_awvalid, s_wvalid, s_bready, busy, m_awready, m_wready, m_bvalid}
                !== 25'b0) fail("traffic during common reset");
        end else begin
            // Case inequality rejects X/Z in every signal used for routing.
            if ((^{s_awvalid, s_wvalid, s_bready, busy, owner, error_flags,
                  m_awready, m_wready, m_bvalid}) === 1'bx)
                fail("unknown control output");
            if (error_flags !== expected_flags || error !== (|expected_flags))
                fail("sticky error flags differ from stimulus scoreboard");
            if (busy !== (model_state != 0)) fail("busy lifecycle mismatch");
            if (model_state != 0 && owner !== model_owner)
                fail("owner changed before B retirement");
            if (s_awvalid !== (model_state == 1)) fail("AWVALID timing mismatch");
            if (s_wvalid !== ((model_state == 2) && m_wvalid[model_owner]))
                fail("W forwarded before AW, after final count, or from nonowner");
            if (s_bready !== ((model_state == 3) && m_bready[model_owner]))
                fail("BREADY before complete W count or from nonowner");
            for (i = 0; i < M; i = i + 1) begin
                if (m_awready[i] !== (model_state == 1 && i == model_owner && s_awready))
                    fail("upstream AW acceptance/leakage");
                if (m_wready[i] !== (model_state == 2 && i == model_owner && s_wready))
                    fail("upstream W acceptance/leakage");
                if (m_bvalid[i] !== (model_state == 3 && i == model_owner && s_bvalid))
                    fail("upstream B acceptance/leakage");
                if (m_bvalid[i] && (m_bid[i*4 +: 4] !== s_bid ||
                                   m_bresp[i*2 +: 2] !== s_bresp))
                    fail("BID/BRESP rewritten");
                if (aw_held[i] && (!m_awvalid[i] || upstream_aw(i) !== previous_aw[i])) begin
                    if (mode == 2 && i == 5) fault_changes = fault_changes + 1;
                    else fail("source AW changed or withdrew before READY");
                end
                if (w_held[i] && (!m_wvalid[i] ||
                    {m_wdata[i*128 +: 128],m_wstrb[i*16 +: 16],m_wlast[i]}
                    !== previous_w[i])) begin
                    // Deliberately malformed extra beats are abandoned by the
                    // fault source after B; legal traffic has no such exception.
                    if (!(mode == 2 && (i == 3 || i == 5) && seq[i] == target[i]))
                        fail("source W changed under backpressure");
                end
                aw_held[i] = m_awvalid[i] && !m_awready[i];
                w_held[i] = m_wvalid[i] && !m_wready[i];
                previous_aw[i] = upstream_aw(i);
                previous_w[i] = {m_wdata[i*128 +: 128],m_wstrb[i*16 +: 16],m_wlast[i]};
            end
            if (slave_aw_held && (!s_awvalid || slave_aw !== previous_slave_aw))
                fail("slave AW changed during stall/new competing request");
            if (slave_w_held && (!s_wvalid ||
                {s_wdata,s_wstrb,s_wlast} !== previous_slave_w))
                fail("slave W changed during stall");
            if (slave_b_held && (!s_bvalid || {s_bid,s_bresp} !== previous_slave_b))
                fail("test slave B violated stable payload contract");
            slave_aw_held = s_awvalid && !s_awready;
            slave_w_held = s_wvalid && !s_wready;
            slave_b_held = s_bvalid && !s_bready;
            previous_slave_aw = slave_aw;
            previous_slave_w = {s_wdata,s_wstrb,s_wlast};
            previous_slave_b = {s_bid,s_bresp};
            if (slave_aw_held) aw_stalls = aw_stalls + 1;
            if (slave_w_held) w_stalls = w_stalls + 1;
            if (model_state == 3 && slave_b_held) b_stalls = b_stalls + 1;
            if ((model_state == 0 || model_state == 1) && |m_wvalid)
                pre_aw_w = pre_aw_w + 1;
            if (model_state == 2 && !m_wvalid[model_owner])
                source_bubbles = source_bubbles + 1;
            if (s_bvalid && model_state != 3) expected_flags[3] = 1;
            if (model_state == 3 && s_bvalid) begin
                if (s_bid != snapshot[64:61]) expected_flags[1] = 1;
                if (s_bresp != 0) expected_flags[2] = 1;
            end
            case (model_state)
                0: begin
                    chosen = -1;
                    for (scan = 0; scan < M; scan = scan + 1) begin
                        candidate = (model_rr + scan) % M;
                        if (chosen < 0 && m_awvalid[candidate]) chosen = candidate;
                    end
                    if (chosen >= 0) begin
                        model_owner = chosen;
                        snapshot = upstream_aw(chosen);
                        model_length = m_awlen[chosen*8 +: 8] + 1;
                        model_beat = 0;
                        age_aw = 0;
                        model_state = 1;
                    end
                end
                1: begin
                    if (slave_aw !== snapshot) fail("AW snapshot mismatch");
                    if (!m_awvalid[model_owner] || upstream_aw(model_owner) !== snapshot)
                        expected_flags[4] = 1;
                    age_aw = age_aw + 1;
                    if (s_awvalid && s_awready) begin
                        if (!m_awvalid[model_owner]) fail("handshake without upstream VALID");
                        aw_count = aw_count + 1;
                        $fdisplay(trace,"A,%0d,%0d,%0d,%08h,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                            model_owner,seq[model_owner],s_awid,s_awaddr,s_awlen,
                            s_awsize,s_awburst,s_awlock,s_awcache,s_awprot,s_awqos,s_awregion);
                        aw_done[model_owner] = 1;
                        age_w = 0;
                        model_state = 2;
                    end
                end
                2: begin
                    age_w = age_w + 1;
                    if (s_wvalid) begin
                        if (s_wdata !== data_for(model_owner,seq[model_owner],model_beat) ||
                            s_wstrb !== strb_for(model_owner,seq[model_owner],model_beat) ||
                            s_wlast !== last_for(model_owner,seq[model_owner],model_beat))
                            fail("W byte/strobe/LAST scoreboard mismatch (no X skipping)");
                    end
                    if (s_wvalid && s_wready) begin
                        if (s_wlast != (model_beat == model_length-1)) expected_flags[0] = 1;
                        $fdisplay(trace,"W,%0d,%0d,%0d,%032h,%04h,%0d",model_owner,
                            seq[model_owner],model_beat,s_wdata,s_wstrb,s_wlast);
                        w_count = w_count + 1;
                        model_beat = model_beat + 1;
                        next_beat[model_owner] = model_beat;
                        if (model_beat == model_length) begin
                            age_b = 0;
                            model_state = 3;
                        end
                    end
                end
                3: begin
                    age_b = age_b + 1;
                    if (s_bvalid && s_bready) begin
                        b_count = b_count + 1;
                        $fdisplay(trace,"B,%0d,%0d,%0d,%0d",model_owner,
                            seq[model_owner],s_bid,s_bresp);
                        seq[model_owner] = seq[model_owner] + 1;
                        aw_done[model_owner] = 0;
                        next_beat[model_owner] = 0;
                        model_rr = (model_owner + 1) % M;
                        model_state = 0;
                    end
                end
            endcase
        end
    end

    task automatic clear_inputs;
        begin
            m_awid = 0; m_awaddr = 0; m_awlen = 0; m_awsize = 0;
            m_awburst = 0; m_awlock = 0; m_awcache = 0; m_awprot = 0;
            m_awqos = 0; m_awregion = 0; m_awvalid = 0;
            m_wdata = 0; m_wstrb = 0; m_wlast = 0; m_wvalid = 0; m_bready = 0;
            s_awready = 0; s_wready = 0; s_bvalid = 0; s_bid = 0; s_bresp = 0;
        end
    endtask
    task automatic common_reset;
        begin
            @(negedge clk);
            rst_n = 0;
            clear_inputs();
            $fdisplay(trace,"R,%0d",cycles);
            repeat (3) @(negedge clk);
            rst_n = 1;
        end
    endtask
    task automatic drive;
        integer master, txn, beat;
        reg offer, changed;
        begin
            for (master = 0; master < M; master = master + 1) begin
                txn = seq[master];
                beat = next_beat[master];
                descriptor(master,txn);
                offer = txn < target[master] && !aw_done[master];
                if (mode == 1 && master == 0 && seq[6] == 0 &&
                    !(model_state == 1 && model_owner == 6 && age_aw >= 3))
                    offer = 0;
                // Once this late arrival asserts VALID it stays asserted.
                if (mode == 1 && master == 0 && aw_held[0]) offer = 1;
                m_awvalid[master] = offer;
                changed = mode == 2 && master == 5 && model_state == 1 &&
                          model_owner == 5 && age_aw >= 2;
                if (changed) begin
                    m_awaddr[master*32 +: 32] = m_awaddr[master*32 +: 32] ^ 32'hffff0000;
                    m_awid[master*4 +: 4] = 4'd3;
                end
                // Poison *all* live AW fields immediately after acceptance.
                // AWLEN/BID checking must still use the original snapshot.
                if (aw_done[master]) begin
                    m_awid[master*4 +: 4] = ~m_awid[master*4 +: 4];
                    m_awaddr[master*32 +: 32] = ~m_awaddr[master*32 +: 32];
                    m_awlen[master*8 +: 8] = ~m_awlen[master*8 +: 8];
                    m_awsize[master*3 +: 3] = ~m_awsize[master*3 +: 3];
                    m_awburst[master*2 +: 2] = ~m_awburst[master*2 +: 2];
                    m_awlock[master] = ~m_awlock[master];
                    m_awcache[master*4 +: 4] = ~m_awcache[master*4 +: 4];
                    m_awprot[master*3 +: 3] = ~m_awprot[master*3 +: 3];
                    m_awqos[master*4 +: 4] = ~m_awqos[master*4 +: 4];
                    m_awregion[master*4 +: 4] = ~m_awregion[master*4 +: 4];
                end
                m_wdata[master*128 +: 128] = data_for(master,txn,beat);
                m_wstrb[master*16 +: 16] = strb_for(master,txn,beat);
                m_wlast[master] = last_for(master,txn,beat);
                m_wvalid[master] = txn < target[master] &&
                    beat < length_for(master,txn) && (w_held[master] || (random_word()%4 != 0));
                // A too-late WLAST is offered as an extra beat, but cannot pass.
                if (mode == 2 && (master == 3 || master == 5) && aw_done[master] &&
                    beat == length_for(master,txn)) begin
                    m_wvalid[master] = 1;
                    m_wlast[master] = 1;
                end
                m_bready[master] = random_word()%3 != 0;
            end
            // Deliberate stalls guarantee coverage; randomized stalls follow.
            s_awready = model_state == 1 && age_aw >= 6 && random_word()%3 != 0;
            if (mode == 1 && model_owner == 6 && age_aw < 12) s_awready = 0;
            s_wready = age_w >= 6 && random_word()%3 != 0;
            // Exercise READY high even before the AW, with all masters offering W.
            if (model_state == 0 || model_state == 1) s_wready = 1;
            s_bvalid = slave_b_held || (model_state == 3 && age_b >= 16 && random_word()%3 != 0);
            if (mode == 2 && model_owner == 4 && model_state == 2 && model_beat >= 1)
                s_bvalid = 1;
            s_bid = id_for(model_owner,seq[model_owner]);
            s_bresp = 0;
            if (mode == 2 && (model_owner == 0 || model_owner == 5)) s_bid = s_bid ^ 4'hf;
            if (mode == 2 && model_owner == 1) s_bresp = 2;
            if (mode == 2 && model_owner == 5) s_bresp = 3;
            if (model_state == 3 && age_b < 24) m_bready[model_owner] = 0;
            if (mode == 1 && m_awvalid[0] && model_owner == 6 && model_state == 1)
                late_arrivals = late_arrivals + 1;
        end
    endtask
    task automatic session(input integer abort_phase);
        integer tick, master, completed;
        reg abort_now;
        begin : run_session
            for (tick = 0; tick < 100000; tick = tick + 1) begin
                @(negedge clk);
                drive();
                abort_now = 0;
                if (abort_phase == 0) abort_now = model_state == 1 && age_aw >= 2 && !s_awready;
                if (abort_phase == 1) abort_now = model_state == 2 && age_w >= 2 && s_wvalid && !s_wready;
                if (abort_phase == 2) abort_now = model_state == 2 && model_beat >= 1;
                if (abort_phase == 3) abort_now = model_state == 3 && age_b >= 3 && !s_bvalid;
                if (abort_phase == 4) abort_now = model_state == 3 && s_bvalid && !s_bready;
                if (abort_now) begin
                    reset_checks = reset_checks + 1;
                    disable run_session;
                end
                completed = 1;
                for (master = 0; master < M; master = master + 1)
                    if (seq[master] != target[master]) completed = 0;
                if (completed && model_state == 0) begin
                    // Keep the bus quiet for several cycles and catch ghost B/grants.
                    repeat (5) begin
                        @(negedge clk);
                        drive();
                    end
                    disable run_session;
                end
            end
            fail("session watchdog: missing data/response or lost owner");
        end
    endtask

    integer master, phase;
    initial begin
        rng = SEED;
        mode = CASE_ID;
        if (!$value$plusargs("TRACE=%s",trace_path)) trace_path = "trace.csv";
        trace = $fopen(trace_path,"w");
        if (!trace) $fatal(1,"cannot create trace");
        clear_inputs();
        for (master = 0; master < M; master = master + 1)
            target[master] = (CASE_ID == 0) ? 32 : 1;
        if (CASE_ID == 1)
            for (master = 1; master < 6; master = master + 1) target[master] = 0;
        common_reset();
        if (CASE_ID == 3) begin
            for (phase = 0; phase < 5; phase = phase + 1) begin
                session(phase);
                common_reset();
                session(-1);
                if (error_flags !== 0) fail("ghost error after common-reset restart");
                if (phase < 4) common_reset();
            end
        end else session(-1);
        if (CASE_ID == 2) begin
            if (error_flags !== 5'b11111 || fault_changes == 0)
                fail("fault injections did not exercise all sticky flags");
        end else if (error_flags !== 0) fail("clean traffic raised error");
        if (aw_stalls == 0 || w_stalls == 0 || b_stalls == 0 || pre_aw_w == 0)
            fail("mandatory backpressure/pre-AW W coverage missing");
        if (CASE_ID == 0 && (b_count != 224 || source_bubbles == 0))
            fail("32 transactions per master/source bubble coverage missing");
        if (CASE_ID == 1 && (b_count != 2 || late_arrivals == 0))
            fail("late higher-priority contender coverage missing");
        if (CASE_ID == 2 && b_count != 7) fail("faulty transactions failed to drain/recover");
        if (CASE_ID == 3 && (reset_checks != 5 || b_count != 35))
            fail("common-reset phases/restarts missing");
        $fclose(trace);
        $display("METRICS aw=%0d w=%0d b=%0d bytes=%0d cycles=%0d aw_stalls=%0d w_stalls=%0d b_stalls=%0d pre_aw_w=%0d source_bubbles=%0d late_arrivals=%0d fault_changes=%0d reset_checks=%0d flags=%0d",
            aw_count,w_count,b_count,w_count*16,cycles,aw_stalls,w_stalls,b_stalls,
            pre_aw_w,source_bubbles,late_arrivals,fault_changes,reset_checks,error_flags);
        $display("PASS fpga_v8_ddr_write_arbiter case=%0d seed=%0d",CASE_ID,SEED);
        $finish;
    end
    initial begin
        #20000000;
        $fatal(1,"global timeout");
    end
endmodule
