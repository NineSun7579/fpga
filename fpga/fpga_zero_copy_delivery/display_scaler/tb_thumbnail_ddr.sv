`timescale 1ns/1ps
module tb_thumbnail_ddr;
    parameter W=640, H=480, STALL=1, HOLD_B=0, FAULT=0;
    localparam PIXELS=W*H, N=(W/2)*(H/2)*2;
    localparam READS=(PIXELS+7)/8, WORDS=(N+15)/16;
    localparam SRC_MEM=((READS+15)/16)*512;
    localparam DST_MEM=((WORDS+15)/16)*512+64;
    localparam SRC=32'h1000, DST=32'h200000;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, cmd_valid=0;
    reg [31:0] src=SRC, dst=DST;
    wire cmd_ready,busy,done,error,config_error;
    wire [31:0] araddr,awaddr;
    wire [7:0] arlen,awlen;
    wire [2:0] arsize,awsize;
    wire [1:0] arburst,awburst;
    wire arvalid,rready,awvalid,wlast,wvalid,bready;
    reg arready=0,awready=0,wready=0,rvalid=0,rlast=0,bvalid=0;
    reg [127:0] rdata=0;
    reg [1:0] rresp=0,bresp=0;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    display_thumbnail_ddr #(.WIDTH(W),.HEIGHT(H)) dut (
        .clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_src(src),.cmd_dst(dst),.busy(busy),.done(done),.error(error),
        .config_error(config_error),.m_axi_araddr(araddr),.m_axi_arlen(arlen),
        .m_axi_arsize(arsize),.m_axi_arburst(arburst),.m_axi_arvalid(arvalid),
        .m_axi_arready(arready),.m_axi_rdata(rdata),.m_axi_rresp(rresp),
        .m_axi_rlast(rlast),.m_axi_rvalid(rvalid),.m_axi_rready(rready),
        .m_axi_awaddr(awaddr),.m_axi_awlen(awlen),.m_axi_awsize(awsize),
        .m_axi_awburst(awburst),.m_axi_awvalid(awvalid),.m_axi_awready(awready),
        .m_axi_wdata(wdata),.m_axi_wstrb(wstrb),.m_axi_wlast(wlast),
        .m_axi_wvalid(wvalid),.m_axi_wready(wready),.m_axi_bresp(bresp),
        .m_axi_bvalid(bvalid),.m_axi_bready(bready));

    // Physical byte arrays model HMIC word addresses, not linear AXI bytes.
    // CPU fixture leaves poisoned half-slots between camera burst payloads.
    reg [7:0] source_mem[0:SRC_MEM-1];
    reg [7:0] dest_mem[0:DST_MEM-1];
    integer cycle=0,read_count=0,write_count=0,ar_count=0,aw_count=0;
    integer rd_left=0,rd_beat=0,rd_len=0,rd_delay=-1,wr_delay=-1;
    integer wr_beats=0,staged_count=0,j,k,offset,fd;
    reg read_active=0,got_aw=0,got_w=0;
    reg [31:0] saved_ar,saved_aw;
    reg [127:0] staged_w[0:15];
    reg [15:0] staged_strb[0:15];
    reg [31:0] rng=32'h91827364;
    reg inject=1, fault_seen=0, late_last=0;
    reg saw_early_b=0,saw_final_b_wait=0,saw_tail_wait=0,saw_shared_fault=0;
    reg prev_arstall=0,prev_awstall=0,prev_wstall=0;
    reg [41:0] prev_ar,prev_aw;
    reg [144:0] prev_w;

    always @(negedge clk) begin
        rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
        arready=rst_n && (!STALL || rng[0]);
        // Force read fault to happen with announced, unaccepted write channels.
        awready=rst_n && (!STALL || rng[1]) && !(inject && FAULT==1 && !error);
        wready=rst_n && (!STALL || rng[2]) && !(inject && FAULT==1 && !error);
    end

    always @(posedge clk) begin
        cycle=cycle+1;
        if (cycle>10000000) $fatal(1,"FAIL watchdog");
        if (!rst_n) begin
            rvalid<=0; bvalid<=0; rresp<=0; bresp<=0;
            rd_delay=-1; wr_delay=-1; read_active=0;
            got_aw=0; got_w=0; read_count=0; write_count=0;
            ar_count=0; aw_count=0; rd_left=0; staged_count=0;
            prev_arstall=0; prev_awstall=0; prev_wstall=0;
            fault_seen=0; late_last=0;
            for (j=0;j<DST_MEM;j=j+1) dest_mem[j]=8'ha5;
        end else begin
            if (prev_arstall && (!arvalid || {araddr,arlen,arburst}!==prev_ar))
                $fatal(1,"FAIL AR stalled payload");
            if (prev_awstall && (!awvalid || {awaddr,awlen,awburst}!==prev_aw))
                $fatal(1,"FAIL AW stalled payload");
            if (prev_wstall && (!wvalid || {wlast,wstrb,wdata}!==prev_w))
                $fatal(1,"FAIL W stalled payload");
            prev_arstall=arvalid&&!arready; prev_ar={araddr,arlen,arburst};
            prev_awstall=awvalid&&!awready; prev_aw={awaddr,awlen,awburst};
            prev_wstall=wvalid&&!wready; prev_w={wlast,wstrb,wdata};
            if (error && cmd_ready) $fatal(1,"FAIL fault admitted command");
            if (arvalid && arready) begin
                if (read_active || rvalid) $fatal(1,"FAIL overlapping read");
                if (araddr!==SRC+ar_count*256 ||
                    arlen!=(READS-read_count>=16 ? 15 : READS-read_count-1) ||
                    arsize!=4 || arburst!=1 || araddr[7:0]!=0)
                    $fatal(1,"FAIL AR native burst contract");
                saved_ar=araddr; rd_left=arlen+1; rd_len=arlen;
                rd_beat=0; read_active=1; ar_count=ar_count+1;
                rd_delay=inject && FAULT==1 && read_count>=64 ? 24 : (STALL ? rng[5:3] : 0);
            end
            if (rvalid && rready) begin
                read_count=read_count+1; rd_left=rd_left-1;
                rvalid<=0;
                if (rresp!=0 || (rlast!=(rd_beat==rd_len))) fault_seen=1;
                if (rlast) begin read_active=0; rd_delay=-1; end
                else begin rd_beat=rd_beat+1; rd_delay=STALL ? rng[5:3] : 0; end
            end else if (read_active && !rvalid) begin
                if (rd_delay>0) rd_delay=rd_delay-1;
                else begin
                    // Independent physical address: native words -> bytes,
                    // +16 bytes per beat within this one announced burst.
                    offset=(saved_ar-SRC)*2+rd_beat*16;
                    for (k=0;k<16;k=k+1) begin
                        if (offset+k<SRC_MEM) rdata[k*8 +:8]<=source_mem[offset+k];
                        else rdata[k*8 +:8]<=8'hd3;
                    end
                    rresp<=0; rlast<=(rd_beat==rd_len);
                    if (inject && FAULT==1 && read_count==64) begin
                        if (!awvalid || !wvalid) $fatal(1,"FAIL R fault needs pending AW/W");
                        saw_shared_fault=1; rresp<=2;
                    end
                    if (inject && FAULT==3 && ar_count==1 && rd_beat==2) rlast<=1;
                    if (inject && FAULT==4 && ar_count==1) begin
                        if (rd_beat==rd_len) begin rlast<=0; late_last=1; end
                        if (rd_beat==rd_len+1) rlast<=1;
                    end
                    rvalid<=1;
                end
            end
            if (awvalid && awready) begin
                if (got_aw || awaddr!==DST+aw_count*256 ||
                    awlen!=(WORDS-write_count>=16 ? 15 : WORDS-write_count-1) ||
                    awsize!=4 || awburst!=1 || awaddr[7:0]!=0)
                    $fatal(1,"FAIL AW native burst contract");
                saved_aw=awaddr; wr_beats=awlen+1; got_aw=1; aw_count=aw_count+1;
            end
            if (wvalid && wready) begin
                if (got_w || staged_count>=16) $fatal(1,"FAIL W overflow");
                staged_w[staged_count]=wdata; staged_strb[staged_count]=wstrb;
                staged_count=staged_count+1; got_w=wlast;
            end
            if (got_aw && got_w && wr_delay<0 && !bvalid) begin
                if (staged_count!=wr_beats) $fatal(1,"FAIL WLAST length");
                for (j=0;j<wr_beats;j=j+1) begin
                    offset=(saved_aw-DST)*2+j*16;
                    for (k=0;k<16;k=k+1) begin
                        if (offset+k>=DST_MEM) $fatal(1,"FAIL write range");
                        if (staged_strb[j][k]) dest_mem[offset+k]=staged_w[j][k*8 +:8];
                    end
                    write_count=write_count+1;
                end
                wr_delay=(write_count==WORDS && HOLD_B) ? 2048 : (STALL ? 9 : 0);
                bresp<=inject && FAULT==2 ? 2 : 0;
            end else if (wr_delay>0) begin
                wr_delay=wr_delay-1;
                if (write_count==WORDS && dut.pixels_taken==PIXELS) begin
                    saw_final_b_wait=1;
                    if (done || !busy) $fatal(1,"FAIL completion before final B");
                end
            end else if (wr_delay==0) begin
                // Exercise B failure while another announced read is live.
                if (!(inject && FAULT==2) || read_active) begin
                    if (inject && FAULT==2) saw_shared_fault=1;
                    bvalid<=1; wr_delay=-1;
                end
            end
            if (bvalid && bready) begin
                if (write_count==WORDS && dut.pixels_taken<PIXELS && bresp==0)
                    saw_early_b=1;
                bvalid<=0; got_aw=0; got_w=0; staged_count=0;
            end
            if (dut.final_b_seen && dut.pixels_taken<PIXELS) begin
                saw_tail_wait=1;
                if (done || !busy) $fatal(1,"FAIL completion before input tail drain");
            end
            if (done && (read_active || rvalid || got_aw || got_w || bvalid ||
                         arvalid || awvalid || wvalid))
                $fatal(1,"FAIL completion before AXI drain");
        end
    end

    task reset_all;
        begin
            @(negedge clk); rst_n=0; cmd_valid=0;
            repeat(4) @(negedge clk);
            rst_n=1; src=SRC; dst=DST;
        end
    endtask
    task command;
        begin
            @(negedge clk); cmd_valid=1;
            do @(posedge clk); while (!cmd_ready);
            @(negedge clk); cmd_valid=0;
        end
    endtask
    task invalid_command(input [31:0] s,input [31:0] d);
        begin
            src=s; dst=d; command();
            if (!done || !error || busy || cmd_ready || arvalid || awvalid || wvalid)
                $fatal(1,"FAIL invalid command rejection");
            cmd_valid=1;
            repeat(8) begin
                @(negedge clk);
                if (cmd_ready || busy || arvalid || awvalid || wvalid || done)
                    $fatal(1,"FAIL invalid-command quarantine");
            end
            reset_all();
        end
    endtask
    initial begin
        $readmemh("source_physical.hex",source_mem);
        reset_all();
        if (W<2 || W>2048 || H<2 || H>2048 || W%2 || H%2) begin
            cmd_valid=1;
            repeat(16) begin
                @(negedge clk);
                if (!config_error || cmd_ready || busy || done || arvalid || awvalid || wvalid)
                    $fatal(1,"FAIL invalid geometry admission");
            end
            $display("PASS CONFIG: invalid geometry blocked W=%0d H=%0d",W,H);
            $finish;
        end
        invalid_command(SRC+1,DST);
        invalid_command(SRC,DST+16);
        invalid_command(SRC,SRC);
        if (PIXELS>128) invalid_command(SRC,SRC+256); // non-identical overlap
        invalid_command(32'h10000000,DST);
        invalid_command(SRC,32'hffffff00); // 33-bit end overflow/range check
        command();
        src=32'h6000; dst=32'h700000; // command values must be latched
        wait(done); @(negedge clk);
        if (FAULT) begin
            if (!error || busy || cmd_ready || !fault_seen && FAULT!=2)
                $fatal(1,"FAIL fault completion/quarantine");
            if ((FAULT==1 || FAULT==2) && !saw_shared_fault)
                $fatal(1,"FAIL missing simultaneous-channel fault test");
            if (FAULT==4 && !late_last) $fatal(1,"FAIL missing late RLAST");
            cmd_valid=1;
            repeat(20) begin
                @(negedge clk);
                if (cmd_ready || busy || done || arvalid || awvalid || wvalid)
                    $fatal(1,"FAIL fault command quarantine");
            end
            inject=0; reset_all(); command(); wait(done); @(negedge clk);
        end
        if (error || busy || !cmd_ready || read_count!=READS || write_count!=WORDS ||
            dut.pixels_taken!=PIXELS)
            $fatal(1,"FAIL successful completion counts");
        if (W==640 && H==480) begin
            if (HOLD_B && !saw_final_b_wait) $fatal(1,"FAIL final B hold not exercised");
            if (!HOLD_B && (!saw_early_b || !saw_tail_wait))
                $fatal(1,"FAIL early final B/input tail barrier not exercised");
        end
        fd=$fopen("dest_physical.hex","w");
        for (j=0;j<DST_MEM;j=j+1) $fdisplay(fd,"%02x",dest_mem[j]);
        $fclose(fd);
        repeat(5) @(negedge clk);
        if (done) $fatal(1,"FAIL done must be a pulse");
        $display("PASS DDR: cycles=%0d reads=%0d writes=%0d earlyB=%0d heldB=%0d tailWait=%0d sharedFault=%0d",
                 cycle,read_count,write_count,saw_early_b,saw_final_b_wait,saw_tail_wait,saw_shared_fault);
        $finish;
    end
endmodule
