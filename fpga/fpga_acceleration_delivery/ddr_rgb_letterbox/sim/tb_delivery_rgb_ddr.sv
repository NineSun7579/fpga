`timescale 1ns/1ps
module tb_delivery_rgb_ddr;
    parameter W=4, H=3, OH=5, TOP=1, STALL=1, FAULT=0;
    localparam N=W*OH*3, WORDS=(N+15)/16, READS=(W*H+7)/8;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0, cmd_valid=0;
    wire cmd_ready,busy,done,error,config_error;
    reg [31:0] src=32'h1000,dst=32'h200000;
    wire [31:0] araddr,awaddr;
    wire [7:0] arlen,awlen;
    wire [2:0] arsize,awsize;
    wire [1:0] arburst,awburst;
    wire arvalid,rready,awvalid,wlast,wvalid,bready;
    reg arready=0,awready=0,wready=0,rvalid=0,rlast=1,bvalid=0;
    reg [127:0] rdata=0;
    reg [1:0] rresp=0,bresp=0;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    delivery_rgb_ddr #(.WIDTH(W),.HEIGHT(H),.OUT_HEIGHT(OH),.TOP_ROWS(TOP)) dut (
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
    reg [7:0] expected[0:N*2-1];
    integer cycle=0,read_count=0,write_count=0,frame=0,fd,i;
    integer rd_delay=-1,wr_delay=-1;
    reg got_aw=0,got_w=0;
    reg [31:0] saved_aw;
    reg [127:0] saved_w;
    reg [15:0] saved_strb;
    reg [127:0] staged_w[0:15];
    reg [15:0] staged_strb[0:15];
    integer rd_left=0,wr_beats=0,staged_count=0,j,physical_offset,logical_offset;
    reg prev_arstall=0,prev_awstall=0,prev_wstall=0;
    reg [31:0] prev_ar,prev_aw;
    reg [127:0] prev_w;
    reg [15:0] prev_strb;
    reg [31:0] rng=32'h12345678;
    // Independent channels, delayed responses, W can precede AW.
    always @(negedge clk) begin
        rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
        arready=rst_n && (!STALL || rng[0]);
        awready=rst_n && (!STALL || rng[1]);
        wready=rst_n && (!STALL || rng[2]);
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if (cycle>10000000) $fatal(1,"FAIL watchdog");
        if (!rst_n) begin
            rvalid<=0; bvalid<=0; rd_delay=-1; wr_delay=-1;
            got_aw=0; got_w=0; read_count=0; write_count=0;
            rd_left=0; staged_count=0;
            prev_arstall=0; prev_awstall=0; prev_wstall=0;
        end else begin
            if (prev_arstall && (!arvalid || araddr!==prev_ar)) $fatal(1,"FAIL AR stall");
            if (prev_awstall && (!awvalid || awaddr!==prev_aw)) $fatal(1,"FAIL AW stall");
            if (prev_wstall && (!wvalid || wdata!==prev_w || wstrb!==prev_strb)) $fatal(1,"FAIL W stall");
            prev_arstall=arvalid&&!arready; prev_ar=araddr;
            prev_awstall=awvalid&&!awready; prev_aw=awaddr;
            prev_wstall=wvalid&&!wready; prev_w=wdata; prev_strb=wstrb;
            if (arvalid && arready) begin
                if (rd_delay>=0 || rvalid) $fatal(1,"FAIL overlapping read");
                if (araddr!==32'h1000+read_count*16 || arlen!=(READS-read_count>=16 ? 15 : READS-read_count-1) || arsize!=4 || arburst!=1)
                    $fatal(1,"FAIL read address/attributes");
                // HMIC native word address -> physical bytes. Camera stores
                // 256 physical bytes per 512-byte slot (burst16, bus stride256).
                physical_offset=(araddr-32'h1000)*2;
                logical_offset=(physical_offset/512)*256+physical_offset%512;
                for (i=0;i<8;i=i+1) rdata[i*16 +:16]<=((logical_offset/2+i) ^ (frame*16'h1357)) & 65535;
                rd_left=arlen+1; rd_delay=STALL ? 3 : 0;
                rresp<=(FAULT==1 && frame==0) ? 2 : 0;
                rlast<=(rd_left==1) && !(FAULT==3 && frame==0);
            end else if (rd_delay>0) rd_delay=rd_delay-1;
            else if (rd_delay==0) begin rvalid<=1; rd_delay=-1; end
            if (rvalid && rready) begin
                read_count=read_count+1; rd_left=rd_left-1; rvalid<=0;
                if (rd_left>0) begin
                    for (i=0;i<8;i=i+1) rdata[i*16 +:16]<=((read_count*8+i) ^ (frame*16'h1357)) & 65535;
                    rlast<=(rd_left==1) && !(FAULT==3 && frame==0);
                    rd_delay=STALL ? 3 : 0;
                end
            end
            if (awvalid && awready) begin
                if (got_aw || awaddr!==32'h200000+write_count*16 || awlen!=(WORDS-write_count>=16 ? 15 : WORDS-write_count-1) || awsize!=4 || awburst!=1)
                    $fatal(1,"FAIL write address/attributes");
                saved_aw=awaddr; got_aw=1;
                wr_beats=awlen+1;
            end
            if (wvalid && wready) begin
                if (got_w || staged_count>=16) $fatal(1,"FAIL overlapping write/last");
                staged_w[staged_count]=wdata; staged_strb[staged_count]=wstrb;
                staged_count=staged_count+1; got_w=wlast;
            end
            if (got_aw && got_w && wr_delay<0 && !bvalid) begin
                if(staged_count!=wr_beats) $fatal(1,"FAIL burst beat count");
                for(j=0;j<wr_beats;j=j+1) begin
                saved_w=staged_w[j]; saved_strb=staged_strb[j];
                // Native HMIC address stride within a burst is eight WORDS.
                physical_offset=(saved_aw-32'h200000)*2+j*16;
                logical_offset=(physical_offset/512)*256+physical_offset%512;
                if (FAULT==0 || frame>0) begin
                    for (i=0;i<16;i=i+1) begin
                        if (write_count*16+i<N) begin
                            if(logical_offset!=write_count*16) $fatal(1,"FAIL physical DDR layout");
                            if (!saved_strb[i] || saved_w[i*8 +:8]!==expected[frame*N+write_count*16+i])
                                $fatal(1,"FAIL RGB byte frame=%0d word=%0d lane=%0d",frame,write_count,i);
                        end else if (saved_strb[i]) $fatal(1,"FAIL tail guard overwritten");
                    end
                end
                $fdisplay(fd,"%0d %08h %032h %04h",frame,saved_aw,saved_w,saved_strb);
                write_count=write_count+1;
                end
                wr_delay=STALL ? 5 : 0;
                bresp<=(FAULT==2 && frame==0) ? 2 : 0;
            end else if (wr_delay>0) wr_delay=wr_delay-1;
            else if (wr_delay==0) begin bvalid<=1; wr_delay=-1; end
            if (bvalid && bready) begin bvalid<=0; got_aw=0; got_w=0; staged_count=0; end
            if (done && (rvalid || rd_delay>=0 || got_aw || got_w || bvalid))
                $fatal(1,"FAIL done before response retirement");
        end
    end
    task command;
        begin
            @(negedge clk); cmd_valid=1;
            do @(posedge clk); while (!cmd_ready);
            @(negedge clk); cmd_valid=0;
        end
    endtask
    task bad_address(input [31:0] s,input [31:0] d);
        begin
            src=s; dst=d; command();
            if (!done || !error || busy || arvalid || awvalid || wvalid)
                $fatal(1,"FAIL address rejection");
            @(negedge clk);
        end
    endtask
    initial begin
        $readmemh("expected.hex",expected);
        fd=$fopen("writes.txt","w");
        repeat(4) @(negedge clk); rst_n=1;
        bad_address(32'h1001,32'h200000);
        bad_address(32'h1010,32'h200000);
        bad_address(32'h1000,32'h1000);
        bad_address(32'h10000000,32'h200000);
        for (frame=0;frame<2;frame=frame+1) begin
            src=32'h1000; dst=32'h200000;
            read_count=0; write_count=0;
            command(); src=32'h4000; dst=32'h600000; // commands must be latched
            wait(done); @(negedge clk);
            if (FAULT!=0 && frame==0) begin
                if (!error || busy || cmd_ready) $fatal(1,"FAIL fault quarantine");
                rst_n=0; repeat(4) @(negedge clk); rst_n=1;
            end else begin
                if (error || busy || read_count!=READS || write_count!=WORDS)
                    $fatal(1,"FAIL completion counts");
                repeat(3) @(negedge clk);
            end
        end
        $fclose(fd); $display("PASS tb_delivery_rgb_ddr cycles=%0d",cycle); $finish;
    end
endmodule
