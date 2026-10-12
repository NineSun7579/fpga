`timescale 1ns/1ps
module tb_fpga_v8_raw_frame_axi_physical;
    parameter integer WIDTH = 4;
    parameter integer HEIGHT = 3;
    parameter integer OUT_HEIGHT = 5;
    parameter integer TOP_ROWS = 1;
    parameter integer FULL = 0;
    parameter integer ID_WIDTH = 4;
    parameter [ID_WIDTH-1:0] AXI_ID = 1;
    parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000;
    localparam integer SRC_BYTES = WIDTH * HEIGHT * 2;
    localparam integer SRC_WORDS = (SRC_BYTES + 15) / 16;
    localparam integer SRC_BUS_BYTES = SRC_WORDS * 16;
    localparam integer OUT_BYTES = WIDTH * OUT_HEIGHT * 3;
    localparam integer DST_WORDS = (OUT_BYTES + 15) / 16;
    localparam integer DST_BUS_BYTES = DST_WORDS * 16;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst_n = 0;
    reg cmd_valid = 0;
    wire cmd_ready, cmd_error, busy, done, error;
    reg [31:0] cmd_src_addr = 0, cmd_dst_addr = 0, cmd_frame_id = 0;
    wire [31:0] active_src_addr, active_dst_addr, active_frame_id, completed_frame_id;
    wire [ID_WIDTH-1:0] arid, awid;
    wire [31:0] araddr, awaddr;
    wire [7:0] arlen, awlen;
    wire [2:0] arsize, awsize, arprot, awprot;
    wire [1:0] arburst, awburst;
    wire arlock, awlock;
    wire [3:0] arcache, awcache, arqos, awqos, arregion, awregion;
    wire arvalid, rready, awvalid, wvalid, wlast, bready;
    reg arready = 0, awready = 0, wready = 0;
    reg [ID_WIDTH-1:0] rid = 0, bid = 0;
    reg [127:0] rdata = 0;
    reg [1:0] rresp = 0, bresp = 0;
    reg rlast = 0, rvalid = 0, bvalid = 0;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    fpga_v8_raw_frame_axi_physical #(
        .WIDTH(WIDTH), .HEIGHT(HEIGHT), .OUT_HEIGHT(OUT_HEIGHT),
        .TOP_ROWS(TOP_ROWS), .ID_WIDTH(ID_WIDTH), .AXI_ID(AXI_ID),
        .DDR_ADDRESS_LIMIT(DDR_ADDRESS_LIMIT)
    ) dut (
        .clk(clk), .rst_n(rst_n), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_src_addr(cmd_src_addr), .cmd_dst_addr(cmd_dst_addr),
        .cmd_frame_id(cmd_frame_id), .cmd_error(cmd_error), .busy(busy),
        .done(done), .error(error), .active_src_addr(active_src_addr),
        .active_dst_addr(active_dst_addr), .active_frame_id(active_frame_id),
        .completed_frame_id(completed_frame_id),
        .m_axi_read_arid(arid), .m_axi_read_araddr(araddr),
        .m_axi_read_arlen(arlen), .m_axi_read_arsize(arsize),
        .m_axi_read_arburst(arburst), .m_axi_read_arlock(arlock),
        .m_axi_read_arcache(arcache), .m_axi_read_arprot(arprot),
        .m_axi_read_arqos(arqos), .m_axi_read_arregion(arregion),
        .m_axi_read_arvalid(arvalid), .m_axi_read_arready(arready),
        .m_axi_read_rid(rid), .m_axi_read_rdata(rdata), .m_axi_read_rresp(rresp),
        .m_axi_read_rlast(rlast), .m_axi_read_rvalid(rvalid), .m_axi_read_rready(rready),
        .m_axi_write_awid(awid), .m_axi_write_awaddr(awaddr),
        .m_axi_write_awlen(awlen), .m_axi_write_awsize(awsize),
        .m_axi_write_awburst(awburst), .m_axi_write_awlock(awlock),
        .m_axi_write_awcache(awcache), .m_axi_write_awprot(awprot),
        .m_axi_write_awqos(awqos), .m_axi_write_awregion(awregion),
        .m_axi_write_awvalid(awvalid), .m_axi_write_awready(awready),
        .m_axi_write_wdata(wdata), .m_axi_write_wstrb(wstrb),
        .m_axi_write_wlast(wlast), .m_axi_write_wvalid(wvalid),
        .m_axi_write_wready(wready), .m_axi_write_bid(bid),
        .m_axi_write_bresp(bresp), .m_axi_write_bvalid(bvalid), .m_axi_write_bready(bready)
    );

    reg [7:0] source_mem [0:SRC_BUS_BYTES-1];
    reg [7:0] golden_mem [0:OUT_BYTES-1];
    reg [7:0] dest_mem [0:DST_BUS_BYTES+15];
    string vector_path, output_path, filename;
    reg [31:0] test_src = 32'h00001000, test_dst = 32'h01000000;
    integer frame_seed = 0, fault_mode = 0;
    reg frame_setup = 0;
    integer cycle = 0;
    integer ar_count = 0, r_count = 0, aw_count = 0, w_count = 0, b_count = 0;
    integer r_delay = 0, b_delay = 0, w_delay = 0, r_offset = 0, w_offset = 0;
    integer i, lane, expected_mask, out_file;
    reg read_pending = 0, aw_pending = 0, b_pending = 0;
    reg final_b_accepted = 0;
    integer final_b_wait_cycles = 0;
    integer frame_cycles = 0, frames_checked = 0;
    integer ar_stalls = 0, aw_stalls = 0, w_stalls = 0;
    integer r_bubbles = 0, b_bubbles = 0;
    integer rejected_commands = 0;

    // Independent channel bubbles, including a long delay of the last B.
    always @(negedge clk) begin
        if (!rst_n) begin
            arready = 0;
            awready = 0;
            wready = 0;
        end else begin
            arready = ((cycle % 7) >= 4);
            awready = ((cycle % 11) >= 6) && !aw_pending && !b_pending && !bvalid;
            wready = ((cycle % 5) >= 3) && aw_pending && (w_delay == 0);
        end
    end

    always @(posedge clk) begin
        if (!rst_n || frame_setup) begin
            cycle <= 0;
            frame_cycles <= 0;
            ar_count <= 0; r_count <= 0; aw_count <= 0; w_count <= 0; b_count <= 0;
            read_pending <= 0; aw_pending <= 0; b_pending <= 0;
            rvalid <= 0; bvalid <= 0;
            r_delay <= 0; b_delay <= 0; w_delay <= 0;
            final_b_accepted <= 0;
            final_b_wait_cycles <= 0;
        end else begin
            cycle <= cycle + 1;
            if (busy) frame_cycles <= frame_cycles + 1;
            if (arvalid && !arready) ar_stalls <= ar_stalls + 1;
            if (awvalid && !awready) aw_stalls <= aw_stalls + 1;
            if (wvalid && !wready) w_stalls <= w_stalls + 1;
            if (read_pending && !rvalid) r_bubbles <= r_bubbles + 1;
            if (b_pending && !bvalid) b_bubbles <= b_bubbles + 1;
            if (arvalid && arready) begin
                if (read_pending || rvalid || ar_count >= SRC_WORDS)
                    $fatal(1, "read outstanding/count violation");
                if (araddr !== test_src + ar_count * 16 || arid !== AXI_ID ||
                    arlen !== 0 || arsize !== 4 || arburst !== 1 || arlock !== 0 ||
                    arcache !== 3 || arprot !== 0 || arqos !== 0 || arregion !== 0)
                    $fatal(1, "bad AR attributes/address");
                if ({32'd0, araddr} + 16 > {32'd0, DDR_ADDRESS_LIMIT})
                    $fatal(1, "AR exceeds configured physical DDR limit");
                read_pending <= 1;
                r_offset <= ar_count * 16;
                r_delay <= 2 + (ar_count % 4);
                ar_count <= ar_count + 1;
            end
            if (read_pending && !rvalid) begin
                if (r_delay != 0) r_delay <= r_delay - 1;
                else begin
                    for (lane = 0; lane < 16; lane = lane + 1)
                        rdata[lane*8 +: 8] <= source_mem[r_offset + lane];
                    rid <= ((fault_mode == 1) && (r_count == 0)) ? (AXI_ID ^ 1) : AXI_ID;
                    rresp <= ((fault_mode == 2) && (r_count == 0)) ? 2'b10 : 0;
                    rlast <= !((fault_mode == 3) && (r_count == SRC_WORDS - 1));
                    rvalid <= 1;
                end
            end
            if (rvalid && rready) begin
                if (!read_pending) $fatal(1, "unexpected R handshake");
                rvalid <= 0;
                read_pending <= 0;
                r_count <= r_count + 1;
            end
            if (aw_pending && w_delay != 0) w_delay <= w_delay - 1;
            if (awvalid && awready) begin
                if (aw_pending || b_pending || bvalid || aw_count >= DST_WORDS)
                    $fatal(1, "write outstanding/count violation");
                if (awaddr !== test_dst + aw_count * 16 || awid !== AXI_ID ||
                    awlen !== 0 || awsize !== 4 || awburst !== 1 || awlock !== 0 ||
                    awcache !== 3 || awprot !== 0 || awqos !== 0 || awregion !== 0)
                    $fatal(1, "bad AW attributes/address");
                if ({32'd0, awaddr} + 16 > {32'd0, DDR_ADDRESS_LIMIT})
                    $fatal(1, "AW exceeds configured physical DDR limit");
                aw_pending <= 1;
                w_delay <= 2;
                w_offset <= aw_count * 16;
                aw_count <= aw_count + 1;
            end
            if (wvalid && wready) begin
                if (!aw_pending || !wlast || w_count >= DST_WORDS)
                    $fatal(1, "W without AW/last/count");
                expected_mask = ((w_count == DST_WORDS - 1) && (OUT_BYTES % 16 != 0)) ?
                                ((1 << (OUT_BYTES % 16)) - 1) : 65535;
                if (wstrb !== expected_mask[15:0])
                    $fatal(1, "WSTRB mismatch beat %0d got %h expected %h", w_count, wstrb, expected_mask);
                for (lane = 0; lane < 16; lane = lane + 1) begin
                    if (wstrb[lane]) begin
                        if (w_offset + lane >= OUT_BYTES)
                            $fatal(1, "write beyond valid output bytes");
                        if (wdata[lane*8 +: 8] !== golden_mem[w_offset + lane])
                            $fatal(1, "byte mismatch seed=%0d offset=%0d got=%h expected=%h",
                                   frame_seed, w_offset + lane, wdata[lane*8 +: 8], golden_mem[w_offset + lane]);
                        dest_mem[w_offset + lane] <= wdata[lane*8 +: 8];
                    end
                end
                aw_pending <= 0;
                b_pending <= 1;
                b_delay <= (w_count == DST_WORDS - 1) ? 80 : 2 + (w_count % 3);
                w_count <= w_count + 1;
            end
            if (b_pending && !bvalid) begin
                if (w_count == DST_WORDS) begin
                    final_b_wait_cycles <= final_b_wait_cycles + 1;
                    if (done || cmd_ready || !busy)
                        $fatal(1, "completion/ready before delayed final B");
                end
                if (b_delay != 0) b_delay <= b_delay - 1;
                else begin
                    bid <= ((fault_mode == 4) && (b_count == DST_WORDS - 1)) ? (AXI_ID ^ 1) : AXI_ID;
                    bresp <= ((fault_mode == 5) && (b_count == DST_WORDS - 1)) ? 2'b10 : 0;
                    bvalid <= 1;
                end
            end
            if (bvalid && bready) begin
                if (!b_pending) $fatal(1, "unexpected B handshake");
                bvalid <= 0;
                b_pending <= 0;
                b_count <= b_count + 1;
                if (b_count == DST_WORDS - 1) final_b_accepted <= 1;
            end
            if (busy && cmd_ready) $fatal(1, "command accepted during busy");
            if (done && (!final_b_accepted || b_count != DST_WORDS ||
                         ar_count != SRC_WORDS || r_count != SRC_WORDS ||
                         aw_count != DST_WORDS || w_count != DST_WORDS ||
                         read_pending || aw_pending || b_pending || rvalid || bvalid))
                $fatal(1, "done before complete drain");
        end
    end

    reg ar_held = 0, aw_held = 0, w_held = 0;
    reg [127:0] saved_ar = 0, saved_aw = 0;
    reg [144:0] saved_w = 0;
    wire [127:0] ar_payload = {arid, araddr, arlen, arsize, arburst, arlock, arcache, arprot, arqos, arregion};
    wire [127:0] aw_payload = {awid, awaddr, awlen, awsize, awburst, awlock, awcache, awprot, awqos, awregion};
    always @(posedge clk) begin
        if (!rst_n) begin
            ar_held <= 0; aw_held <= 0; w_held <= 0;
        end else begin
            if (ar_held && (!arvalid || ar_payload !== saved_ar)) $fatal(1, "AR changed while stalled");
            if (aw_held && (!awvalid || aw_payload !== saved_aw)) $fatal(1, "AW changed while stalled");
            if (w_held && (!wvalid || {wdata, wstrb, wlast} !== saved_w)) $fatal(1, "W changed while stalled");
            ar_held <= arvalid && !arready;
            aw_held <= awvalid && !awready;
            w_held <= wvalid && !wready;
            saved_ar <= ar_payload; saved_aw <= aw_payload;
            saved_w <= {wdata, wstrb, wlast};
        end
    end

    task tick;
        begin @(posedge clk); #2; end
    endtask
    task common_reset;
        begin
            @(negedge clk); rst_n = 0; cmd_valid = 0; frame_setup = 0;
            repeat (4) tick;
            @(negedge clk); rst_n = 1;
            repeat (20) begin
                tick;
                if (done || busy || error || cmd_error || arvalid || awvalid || wvalid || bready || rready)
                    $fatal(1, "ghost activity after common reset");
            end
            if (!cmd_ready || completed_frame_id != 0) $fatal(1, "not idle after reset");
        end
    endtask
    task reject_command(input [31:0] src, input [31:0] dst);
        reg [31:0] old_completed;
        begin
            old_completed = completed_frame_id;
            @(negedge clk);
            if (!cmd_ready) $fatal(1, "not ready for invalid command");
            cmd_src_addr = src; cmd_dst_addr = dst; cmd_frame_id = 32'hbadc0000;
            cmd_valid = 1;
            tick;
            if (!cmd_error || !error || busy || done || arvalid || awvalid || wvalid ||
                completed_frame_id != old_completed) $fatal(1, "invalid command not rejected");
            @(negedge clk); cmd_valid = 0;
            repeat (3) begin
                tick;
                if (busy || done || arvalid || awvalid || wvalid)
                    $fatal(1, "invalid address emitted AXI traffic");
            end
            if (cmd_error || !error || !cmd_ready) $fatal(1, "command error pulse/sticky contract");
            rejected_commands = rejected_commands + 1;
            $display("ADDRESS_REJECT_PASS src=%h dst=%h limit=%h", src, dst, DDR_ADDRESS_LIMIT);
        end
    endtask
    task start_frame(input integer seed, input integer fault, input [31:0] src, input [31:0] dst);
        begin
            @(negedge clk);
            if (!cmd_ready) $fatal(1, "pipeline not idle for new frame");
            frame_seed = seed; fault_mode = fault; test_src = src; test_dst = dst;
            frame_setup = 1;
            filename = $sformatf("%s/source_%0d.hex", vector_path, seed);
            $readmemh(filename, source_mem);
            filename = $sformatf("%s/expected_%0d.hex", vector_path, seed);
            $readmemh(filename, golden_mem);
            for (i = 0; i < DST_BUS_BYTES + 16; i = i + 1) dest_mem[i] = 8'ha5;
            tick;
            @(negedge clk); frame_setup = 0;
            cmd_src_addr = src; cmd_dst_addr = dst; cmd_frame_id = 32'h12340000 + seed;
            cmd_valid = 1;
            tick;
            if (!busy || cmd_error || error || active_src_addr !== src ||
                active_dst_addr !== dst || active_frame_id !== 32'h12340000 + seed)
                $fatal(1, "command snapshot/start mismatch");
            @(negedge clk);
            cmd_valid = 0;
            cmd_src_addr = 32'hfffffff1; cmd_dst_addr = 32'hffffffff; cmd_frame_id = 32'hffffffff;
        end
    endtask
    task finish_frame(input integer seed, input integer expect_error);
        integer timeout_cycles;
        begin
            cmd_valid = 1;
            repeat (5) begin
                tick;
                if (cmd_ready || active_frame_id !== 32'h12340000 + seed ||
                    active_src_addr !== test_src || active_dst_addr !== test_dst)
                    $fatal(1, "command accepted/changed while busy");
            end
            @(negedge clk); cmd_valid = 0;
            timeout_cycles = 0;
            while (!done && timeout_cycles < 6000000) begin
                tick; timeout_cycles = timeout_cycles + 1;
            end
            if (!done || busy || error !== (expect_error != 0) || cmd_error ||
                completed_frame_id !== 32'h12340000 + seed || !cmd_ready ||
                b_count != DST_WORDS || r_count != SRC_WORDS || final_b_wait_cycles < 80)
                $fatal(1, "frame completion mismatch seed=%0d error=%b expected=%0d B=%0d R=%0d",
                       seed, error, expect_error, b_count, r_count);
            filename = $sformatf("%s/output_%0d.hex", output_path, seed);
            out_file = $fopen(filename, "w");
            if (!out_file) $fatal(1, "cannot open output dump");
            for (i = 0; i < OUT_BYTES; i = i + 1) begin
                if (dest_mem[i] !== golden_mem[i]) $fatal(1, "final memory byte mismatch");
                $fdisplay(out_file, "%02x", dest_mem[i]);
            end
            $fclose(out_file);
            for (i = OUT_BYTES; i < DST_BUS_BYTES + 16; i = i + 1)
                if (dest_mem[i] !== 8'ha5) $fatal(1, "unstrobed/guard byte overwritten");
            $display("FRAME_PASS seed=%0d fault=%0d bytes=%0d AR=%0d B=%0d cycles=%0d delayed_last_B=%0d src=%h dst=%h",
                     seed, expect_error, OUT_BYTES, ar_count, b_count, frame_cycles, final_b_wait_cycles,
                     test_src, test_dst);
            frames_checked = frames_checked + 1;
            tick;
            if (done || error !== (expect_error != 0)) $fatal(1, "done pulse/error persistence");
        end
    endtask
    task abort_frame(input integer phase);
        integer watchdog;
        begin
            start_frame(0, 0, 32'h1000, 32'h01000000);
            watchdog = 0;
            case (phase)
                0: while (!(arvalid && !arready) && watchdog < 10000) begin tick; watchdog = watchdog + 1; end
                1: while (!read_pending && watchdog < 10000) begin tick; watchdog = watchdog + 1; end
                2: while (!(awvalid && !awready) && watchdog < 10000) begin tick; watchdog = watchdog + 1; end
                3: while (!(wvalid && !wready) && watchdog < 10000) begin tick; watchdog = watchdog + 1; end
                4: while (!(b_pending && w_count == DST_WORDS) && watchdog < 10000) begin tick; watchdog = watchdog + 1; end
            endcase
            if (watchdog == 10000) $fatal(1, "reset phase not reached: %0d", phase);
            common_reset;
            $display("RESET_PASS phase=%0d", phase);
        end
    endtask

    integer phase;
    initial begin
        if (!$value$plusargs("VECTORS=%s", vector_path)) $fatal(1, "missing VECTORS");
        if (!$value$plusargs("OUTPUT=%s", output_path)) $fatal(1, "missing OUTPUT");
        common_reset;
        if (!FULL) begin
            reject_command(32'h1001, 32'h01000000);
            reject_command(32'h1000, 32'h01000001);
            reject_command(32'h1000, 32'h1000);
            reject_command(32'h1000, 32'h1000 + SRC_BUS_BYTES - 16);
            reject_command(32'h01000000, 32'h01000000 - DST_BUS_BYTES + 16);
            reject_command(DDR_ADDRESS_LIMIT, 32'h01000000);
            reject_command(32'h1000, DDR_ADDRESS_LIMIT);
            reject_command(DDR_ADDRESS_LIMIT - SRC_BUS_BYTES + 16, 32'h01000000);
            reject_command(32'h1000, DDR_ADDRESS_LIMIT - DST_BUS_BYTES + 16);
            reject_command(32'hfffffff0, 32'h01000000);
            reject_command(32'h1000, 32'hfffffff0);
            // Crossbar decode is not the physical DDR addressability limit.
            reject_command(32'h20000000, 32'h01000000);
            reject_command(32'h1000, 32'h20000000);
            reject_command(32'h10001000, 32'h01000000);
            reject_command(32'h1000, 32'h10001000);
            for (phase = 0; phase < 3; phase = phase + 1) begin
                start_frame(phase, 0, 32'h1000 + phase * 16, 32'h01000000 + phase * 16);
                finish_frame(phase, 0);
            end
            for (phase = 1; phase <= 5; phase = phase + 1) begin
                start_frame(phase + 2, phase, 32'h1000, 32'h01000000);
                finish_frame(phase + 2, 1);
            end
            start_frame(8, 0, DDR_ADDRESS_LIMIT - SRC_BUS_BYTES, 32'h01000000);
            finish_frame(8, 0);
            start_frame(9, 0, 32'h1000, 32'h1000 + SRC_BUS_BYTES);
            finish_frame(9, 0);
            for (phase = 0; phase < 5; phase = phase + 1) begin
                abort_frame(phase);
                start_frame(10 + phase, 0, 32'h1000, 32'h01000000);
                finish_frame(10 + phase, 0);
            end
            start_frame(15, 0, 32'h1000, DDR_ADDRESS_LIMIT - DST_BUS_BYTES);
            finish_frame(15, 0);
        end else begin
            start_frame(0, 0, 32'h1000, 32'h01000000);
            finish_frame(0, 0);
        end
        if (ar_stalls == 0 || aw_stalls == 0 || w_stalls == 0 || r_bubbles == 0 || b_bubbles == 0)
            $fatal(1, "missing channel stall/bubble coverage AR=%0d AW=%0d W=%0d R=%0d B=%0d",
                   ar_stalls, aw_stalls, w_stalls, r_bubbles, b_bubbles);
        $display("AXI_RAW_PHYSICAL_PASS frames=%0d rejected=%0d limit=%h ar_stalls=%0d aw_stalls=%0d w_stalls=%0d r_bubbles=%0d b_bubbles=%0d",
                 frames_checked, rejected_commands, DDR_ADDRESS_LIMIT,
                 ar_stalls, aw_stalls, w_stalls, r_bubbles, b_bubbles);
        $finish;
    end
    initial begin
        #100000000;
        $fatal(1, "global timeout");
    end
endmodule
