`timescale 1ns/1ps
module tb_capture_lease;
    parameter WORDS = 2048;
    parameter WIDTH = 128;
    parameter HOST_REQUIRED = 1;
    parameter BAD_CFG = 0;
    localparam PIXELS = WORDS*8;
    localparam HEIGHT = PIXELS/WIDTH;
    localparam B0 = 32'h01800000;
    localparam B1 = BAD_CFG == 1 ? B0 + 16 :
                    BAD_CFG == 2 ? 32'h0ffff000 :
                    BAD_CFG == 3 ? 32'h01a00001 : 32'h01a00000;
    localparam DW = BAD_CFG == 5 ? 24 : 16;
    localparam LENGTH = BAD_CFG == 6 ? WORDS*16-16 : WORDS*16;
    reg clk = 0;
    always #5 clk = ~clk;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    reg rst=1, sv=0, pv=0;
    reg [DW-1:0] pixel=0;
    reg cfgv=0;
    reg [31:0] cfggen=0;
    wire cfgr, cfga, cfgx, epoch, armed, cfgok, block_capture;
    wire admit, bank, publish, retire, idle, flush, good, overflow;
    wire [31:0] pubseq, state, last_cnt, diag;
    wire [1:0] bstate0, bstate1;
    wire fault;
    wire [31:0] pub_count, fail_count, reject_count;
    wire [31:0] ca, cl, awaddr;
    wire cv, cr, dv, dr, done, aborted, abort_req, av, ar, wv, wr, wl, br;
    wire [127:0] data, wd;
    wire [15:0] credits, ws;
    wire [7:0] al;
    wire [2:0] aws;
    wire [1:0] awburst, req;
    reg [1:0] ack=0;
    wire iv, hv, raw;
    reg ir=0, hr=0;
    wire [31:0] ia, il, iseq, igen, ha, hl, hseq, hgen;
    wire [63:0] itoken, htoken;
    wire [2:0] icam, hcam;
    wire ibank, hbank;
    reg rv=0, hrv=0;
    wire rr, hrr, ra, rx, hra, hrx;
    reg [2:0] rcam=4, hrcam=4;
    reg rbank=0, hrbank=0;
    reg [31:0] rseq=0, rgen=0, hrseq=0, hrgen=0;
    reg [63:0] rtoken=0, hrtoken=0;
    fpga_v8_capture_lease #(.CAM_DATA_LEN(WORDS), .RAW_LENGTH(LENGTH),
        .FRAME_WIDTH(WIDTH), .FRAME_HEIGHT(HEIGHT), .DATA_WIDTH(DW),
        .BANK0_ADDR(B0), .BANK1_ADDR(B1), .HOST_REQUIRED(HOST_REQUIRED)) manager (
        .clk(clk), .rst(rst), .config_valid(cfgv), .config_ready(cfgr),
        .config_generation(cfggen), .config_accept(cfga), .config_reject(cfgx),
        .epoch_start(epoch), .armed(armed), .config_ok(cfgok),
        .engine_idle(idle), .capture_bank(bank), .admitted_sof(admit),
        .publish(publish), .publish_seq(pubseq), .retired_error(retire),
        .lease_block(block_capture), .bank0_state(bstate0), .bank1_state(bstate1),
        .protocol_fault(fault), .input_valid(iv), .input_ready(ir), .input_raw_valid(raw),
        .input_src_addr(ia), .input_length(il), .input_seq(iseq), .input_generation(igen),
        .input_camera(icam), .input_bank(ibank), .input_token(itoken),
        .release_valid(rv), .release_ready(rr), .release_camera(rcam), .release_bank(rbank),
        .release_seq(rseq), .release_generation(rgen), .release_token(rtoken),
        .release_accept(ra), .release_reject(rx),
        .host_valid(hv), .host_ready(hr), .host_src_addr(ha), .host_length(hl),
        .host_seq(hseq), .host_generation(hgen), .host_camera(hcam),
        .host_bank(hbank), .host_token(htoken), .host_release_valid(hrv),
        .host_release_ready(hrr), .host_release_camera(hrcam), .host_release_bank(hrbank),
        .host_release_seq(hrseq), .host_release_generation(hrgen), .host_release_token(hrtoken),
        .host_release_accept(hra), .host_release_reject(hrx),
        .published_count(pub_count), .failed_count(fail_count),
        .rejected_release_count(reject_count)
    );
    fpga_v8_capture_ov5640_ddr #(.CAM_DATA_LEN(WORDS), .DATA_WIDTH(DW),
        .BANK0_ADDR(B0), .BANK1_ADDR(B1)) camera (
        .axi_clk(clk), .axi_rst(rst), .epoch_start(epoch), .lease_block(block_capture),
        .dma_abort(aborted), .dma_abort_req(abort_req), .dma_done(done),
        .axi_data_available(credits), .axi_cam_en(1'b1),
        .s_data(pixel), .s_data_valid(pv), .s_hsync(1'b1), .s_vsync(sv),
        .axi_data(data), .axi_data_valid(dv), .axi_data_last(), .axi_data_ready(dr),
        .axi_cmd_addr(ca), .axi_cmd_len(cl), .axi_cmd_valid(cv), .axi_cmd_ready(cr),
        .xdma_req(req), .xdma_ack(ack), .admitted_sof(admit), .capture_bank(bank),
        .publish(publish), .publish_seq(pubseq), .retired_error(retire), .engine_idle(idle),
        .capture_flush_o(flush), .frame_good_o(good), .capture_overflow_o(overflow),
        .dbg_fault_snapshot(), .dbg_reject_counts(diag), .dbg_input_pixels(),
        .dbg_axi_cnt(), .dbg_axi_num(), .dbg_zdin(), .dbg_zout(),
        .dbg_state(state), .dbg_last_cnt(last_cnt), .dbg_wd_cnt()
    );
    reg stall_aw=0, stall_w=0, stall_b=0, stall_tag_b=0;
    reg tag_error=0, data_error=0;
    reg bus_active=0, cur_tag=0;
    reg bv=0;
    reg [1:0] resp=0;
    axi_dma_write #(.WAIT_FOR_DATA(1), .BURST_LEN(16), .WD_LIMIT(512)) dma (
        .clk(clk), .rst(rst), .abort_req(abort_req), .data_in_abort(aborted),
        .data_in_available(credits), .cmd_addr(ca), .cmd_len(cl), .cmd_valid(cv),
        .cmd_ready(cr), .cmd_id(4'd3), .data_in(data), .data_in_keep(16'hffff),
        .data_in_valid(dv), .data_in_ready(dr), .data_in_last(done),
        .m_axi_awaddr(awaddr), .m_axi_awlen(al), .m_axi_awvalid(av), .m_axi_awready(ar),
        .m_axi_awsize(aws), .m_axi_awburst(awburst), .m_axi_awid(),
        .m_axi_awlock(), .m_axi_awcache(), .m_axi_awprot(),
        .m_axi_wdata(wd), .m_axi_wstrb(ws), .m_axi_wlast(wl), .m_axi_wvalid(wv),
        .m_axi_wready(wr), .m_axi_bvalid(bv && !stall_b && !(cur_tag && stall_tag_b)),
        .m_axi_bready(br), .m_axi_bresp(resp), .m_axi_bid(4'd3)
    );
    integer cycle=0, left=0, bdelay=0, offset=0, burst_addr=0;
    integer aw_count=0, b_count=0, w_count=0, abort_count=0, checks=0;
    assign ar = !stall_aw && !bus_active && !bv && cycle%5!=0 && cycle%17!=0;
    assign wr = !stall_w && bus_active && cycle%7!=0 && cycle%13!=0;
    reg aw_held=0, w_held=0, i_held=0, h_held=0, reset_seen=0;
    reg [39:0] aw_saved;
    reg [144:0] w_saved;
    reg [196:0] i_saved, h_saved;
    wire [196:0] ipayload={raw,ia,il,iseq,igen,icam,ibank,itoken};
    wire [196:0] hpayload={1'b1,ha,hl,hseq,hgen,hcam,hbank,htoken};
    integer trace;
    reg logcfg, logr, loghr;
    reg [102:0] state_saved;
    wire [102:0] state_now={bstate0,bstate1,armed,fault,pub_count,fail_count,reject_count,1'b0};
    always @(posedge clk) begin
        cycle=cycle+1;
        logcfg=0; logr=0; loghr=0;
        if(rst) begin
            if(!reset_seen) $fdisplay(trace,"R %0d",cycle);
            reset_seen=1;
            bv<=0; bus_active<=0; left=0; bdelay=0;
            aw_held<=0; w_held<=0; i_held<=0; h_held<=0;
        end else begin
            reset_seen=0;
            if(aw_held && (!av || {awaddr,al} !== aw_saved)) $fatal(1,"AW changed while stalled");
            if(w_held && (!wv || {wd,ws,wl} !== w_saved)) $fatal(1,"W changed while stalled");
            if(i_held && (!iv || ipayload !== i_saved)) $fatal(1,"cooperative descriptor unstable");
            if(h_held && (!hv || hpayload !== h_saved)) $fatal(1,"host descriptor unstable");
            aw_held<=av&&!ar; aw_saved<={awaddr,al};
            w_held<=wv&&!wr; w_saved<={wd,ws,wl};
            i_held<=iv&&!ir; i_saved<=ipayload;
            h_held<=hv&&!hr; h_saved<=hpayload;
            if(done && aborted) $fatal(1,"DMA success and failure overlap");
            if(flush && (dma.trans || av || wv || bus_active || bv)) $fatal(1,"flush before retirement");
            if(fault) $fatal(1,"manager protocol fault");
            if(admit) $fdisplay(trace,"A %0d",bank);
            if(cv&&cr) $fdisplay(trace,"M %08h %0d",ca,cl);
            if(av&&ar) begin
                if(bus_active||bv) $fatal(1,"multiple AXI obligations");
                if(aws!==3'd4||awburst!==2'd1||al>15) $fatal(1,"bad AXI shape");
                if((bstate0==2&&awaddr>=B0&&awaddr<B0+WORDS*16+16)||
                   (bstate1==2&&awaddr>=B1&&awaddr<B1+WORDS*16+16)) $fatal(1,"AW targets held bank");
                aw_count=aw_count+1; left=al+1; offset=awaddr; burst_addr=awaddr;
                bus_active<=1;
                cur_tag=(awaddr==B0+WORDS*16)||(awaddr==B1+WORDS*16);
                $fdisplay(trace,"AW %08h %0d",awaddr,left);
            end
            if(wv&&wr) begin
                if(!bus_active||left==0) $fatal(1,"W without accepted AW");
                if($isunknown({wd,ws,wl})) $fatal(1,"X/Z anywhere in 128-bit W payload/strobe/last");
                if(wl!==(left==1)) $fatal(1,"WLAST mismatch");
                $fdisplay(trace,"W %08h %032h %04h %0d",offset,wd,ws,wl);
                w_count=w_count+1; offset=offset+16; left=left-1;
                if(left==0) begin
                    bdelay=2+cycle%19;
                    resp<=((cur_tag&&tag_error)||(!cur_tag&&data_error))?2'b10:0;
                end
            end
            if(bdelay>0) begin bdelay=bdelay-1; if(bdelay==0)bv<=1; end
            if(bv&&!stall_b&&!(cur_tag&&stall_tag_b)&&br) begin
                bv<=0; bus_active<=0; b_count=b_count+1;
                $fdisplay(trace,"B %08h %0d",burst_addr,resp);
            end
            if(publish) $fdisplay(trace,"P %0d %0d",bank,pubseq);
            if(retire) begin abort_count=abort_count+1; $fdisplay(trace,"E"); end
            if(iv&&!i_held) $fdisplay(trace,"O C %0d %0d %0d %08h %0d %016h %0d %0d",ibank,iseq,igen,ia,il,itoken,icam,raw);
            if(hv&&!h_held) $fdisplay(trace,"O H %0d %0d %0d %08h %0d %016h %0d 1",hbank,hseq,hgen,ha,hl,htoken,hcam);
            if(iv&&ir) $fdisplay(trace,"D C %0d %0d %0d %08h %0d %016h %0d %0d",ibank,iseq,igen,ia,il,itoken,icam,raw);
            if(hv&&hr) $fdisplay(trace,"D H %0d %0d %0d %08h %0d %016h %0d 1",hbank,hseq,hgen,ha,hl,htoken,hcam);
            if(cfgv&&cfgr) logcfg=1;
            if(rv&&rr) logr=1;
            if(hrv&&hrr) loghr=1;
        end
        #1;
        if(logcfg) $fdisplay(trace,"C %0d %0d %0d",cfggen,cfga,cfgx);
        if(logr) $fdisplay(trace,"L C %0d %0d %0d %0d %016h %0d %0d",rcam,rbank,rseq,rgen,rtoken,ra,rx);
        if(loghr) $fdisplay(trace,"L H %0d %0d %0d %0d %016h %0d %0d",hrcam,hrbank,hrseq,hrgen,hrtoken,hra,hrx);
        if(state_now!==state_saved) begin
            $fdisplay(trace,"S %0d %0d %0d %0d %0d %0d %0d",bstate0,bstate1,armed,fault,pub_count,fail_count,reject_count);
            state_saved=state_now;
        end
    end
    task sof;
        begin
            @(negedge clk); sv=1;
            repeat(6)@(negedge clk); sv=0;
            repeat(6)@(negedge clk);
        end
    endtask
    function [15:0] pattern(input integer seed, input integer index);
        // Nontrivial RGB565 values across row boundaries and all eight lanes.
        pattern=(seed*7919 + index*73 + (index/WIDTH)*1237 + ((index%WIDTH)^16'h55aa)) & 65535;
    endfunction
    task frame(input integer seed, input integer count);
        integer i;
        begin
            $fdisplay(trace,"F %0d %0d",seed,count);
            sof();
            for(i=0;i<count;i=i+1) begin
                pixel=pattern(seed,i); pv=1; @(negedge clk);
                // Sensor never reads ready. Include sparse pixels regularly.
                if(i%79==31) begin pv=0; @(negedge clk); end
            end
            pv=0;
        end
    endtask
    task quiet;
        begin wait(idle); repeat(12)@(negedge clk); end
    endtask
    task arm(input [31:0] generation, input integer accept_expected);
        begin
            quiet(); @(negedge clk); cfggen=generation; cfgv=1;
            wait(cfgr); @(posedge clk); #2;
            if(cfga!==accept_expected || cfgx!==!accept_expected) $fatal(1,"config outcome");
            @(negedge clk); cfgv=0; quiet(); checks=checks+1;
        end
    endtask
    task finish_good(input integer seq);
        begin wait(last_cnt==seq); quiet(); if(pubseq!==seq+1) $fatal(1,"tag/sequence mismatch"); checks=checks+1; end
    endtask
    task claim(input integer host, input integer bank_expected, input [31:0] seq_expected, input [31:0] generation);
        begin
            if(host) begin
                wait(hv); if(hbank!==bank_expected||hseq!==seq_expected||hgen!==generation) $fatal(1,"host order");
                @(negedge clk); hr=1; @(negedge clk); hr=0;
            end else begin
                wait(iv); if(ibank!==bank_expected||iseq!==seq_expected||igen!==generation||raw!==1) $fatal(1,"coop order");
                @(negedge clk); ir=1; @(negedge clk); ir=0;
            end
            checks=checks+1;
        end
    endtask
    task release_one(input integer host, input integer camera_id, input integer bank_id,
                     input [31:0] seq, input [31:0] generation, input [63:0] token, input integer accepted);
        begin
            @(negedge clk);
            if(host) begin
                hrcam=camera_id; hrbank=bank_id; hrseq=seq; hrgen=generation; hrtoken=token; hrv=1;
                @(posedge clk); #2;
                if(hra!==accepted||hrx!==!accepted) $fatal(1,"host release outcome seq=%0d",seq);
                @(negedge clk); hrv=0;
            end else begin
                rcam=camera_id; rbank=bank_id; rseq=seq; rgen=generation; rtoken=token; rv=1;
                @(posedge clk); #2;
                if(ra!==accepted||rx!==!accepted) $fatal(1,"coop release outcome seq=%0d",seq);
                @(negedge clk); rv=0;
            end
            checks=checks+1;
        end
    endtask
    task release_both(input integer bank_id, input [31:0] seq, input [31:0] generation);
        begin
            release_one(0,4,bank_id,seq,generation,{generation,seq},1);
            if(HOST_REQUIRED) release_one(1,4,bank_id,seq,generation,{generation,seq},1);
        end
    endtask
    task release_parallel(input integer bank_id, input [31:0] seq, input [31:0] generation,
                          input integer wrong_token);
        begin
            @(negedge clk);
            rcam=4; rbank=bank_id; rseq=seq; rgen=generation;
            hrcam=4; hrbank=bank_id; hrseq=seq; hrgen=generation;
            rtoken={generation,seq} ^ wrong_token;
            hrtoken={generation,seq} ^ wrong_token;
            rv=1; hrv=1;
            @(posedge clk); #2;
            if(ra !== (wrong_token == 0) || hra !== (wrong_token == 0) ||
               rx !== (wrong_token != 0) || hrx !== (wrong_token != 0))
                $fatal(1,"parallel release outcomes");
            @(negedge clk); rv=0; hrv=0; checks=checks+1;
        end
    endtask
    task claim_and_release(input integer bank_id, input [31:0] seq, input [31:0] generation);
        begin
            claim(0,bank_id,seq,generation);
            if(HOST_REQUIRED) claim(1,bank_id,seq,generation);
            release_both(bank_id,seq,generation);
        end
    endtask
    task drop_frame(input integer seed);
        integer before_aw, before_pub;
        begin
            before_aw=aw_count; before_pub=pub_count;
            frame(seed,PIXELS); repeat(20)@(negedge clk);
            if(aw_count!=before_aw||pub_count!=before_pub) $fatal(1,"blocked frame wrote or published");
            checks=checks+1;
        end
    endtask
    integer a, p, q;
    initial begin
        trace=$fopen("trace.txt","w");
        state_saved='x;
        repeat(8)@(negedge clk); rst=0; quiet();
        if(BAD_CFG) begin
            if(cfgok!==0) $fatal(1,"invalid parameter accepted");
            arm(41,0); drop_frame(0);
            if(armed||iv||hv||aw_count) $fatal(1,"invalid layout admitted capture");
        end else if(!HOST_REQUIRED) begin
            drop_frame(0); arm(0,0); arm(41,1);
            frame(1,PIXELS); finish_good(1);
            if(hv) $fatal(1,"unexpected host offer in coop-only mode");
            release_one(1,4,0,1,41,{32'd41,32'd1},0);
            claim_and_release(0,1,41);
            if(bstate0!==0) $fatal(1,"coop-only release did not free");
            frame(2,PIXELS); finish_good(2); claim_and_release(1,2,41);
        end else begin
            drop_frame(0); arm(0,0); arm(41,1);
            frame(1,PIXELS); finish_good(1);
            release_one(0,4,0,1,41,{32'd41,32'd1},0);
            release_one(1,4,0,1,41,{32'd41,32'd1},0);
            @(negedge clk); cfgv=1; cfggen=42; repeat(10)@(negedge clk);
            if(cfgr) $fatal(1,"config ready with outstanding lease"); cfgv=0;
            frame(2,PIXELS); finish_good(2); drop_frame(3);
            claim(0,0,1,41); claim(1,0,1,41);
            release_one(0,3,0,1,41,{32'd41,32'd1},0);
            release_one(1,3,0,1,41,{32'd41,32'd1},0);
            release_one(0,4,1,1,41,{32'd41,32'd1},0);
            release_one(1,4,1,1,41,{32'd41,32'd1},0);
            release_one(0,4,0,2,41,{32'd41,32'd2},0);
            release_one(1,4,0,2,41,{32'd41,32'd2},0);
            release_one(0,4,0,1,40,{32'd40,32'd1},0);
            release_one(1,4,0,1,40,{32'd40,32'd1},0);
            release_one(0,4,0,1,41,{32'd41,32'd1}^64'h100,0);
            release_one(1,4,0,1,41,{32'd41,32'd1}^64'h100,0);
            release_one(0,4,0,1,41,{32'd41,32'd1},1);
            release_one(0,4,0,1,41,{32'd41,32'd1},0); drop_frame(4);
            release_one(1,4,0,1,41,{32'd41,32'd1},1);
            claim(0,1,2,41); claim(1,1,2,41);
            frame(5,PIXELS); finish_good(3);
            ack=3; repeat(3)@(negedge clk); ack=0;
            release_one(0,4,0,1,41,{32'd41,32'd1},0);
            release_one(1,4,0,1,41,{32'd41,32'd1},0);
            claim(0,0,3,41); claim(1,0,3,41);
            release_one(1,4,1,2,41,{32'd41,32'd2},1); drop_frame(6);
            release_one(0,4,1,2,41,{32'd41,32'd2},1);
            release_both(0,3,41);
            // Short frame, AW advertised then delayed; retire only after B.
            a=abort_count; p=pub_count; stall_aw=1; stall_b=1;
            frame(7,129); wait(av); sof(); repeat(40)@(negedge clk);
            if(abort_count!=a||bstate1!==1||flush) $fatal(1,"short/AW freed early");
            stall_aw=0; wait(bv); drop_frame(8);
            if(abort_count!=a||bstate1!==1||flush) $fatal(1,"short/B freed early");
            stall_b=0; wait(abort_count==a+1); quiet();
            if(pub_count!=p||bstate1!==0||diag[15:0]==0) $fatal(1,"short published or failed to recover");
            frame(9,PIXELS); finish_good(4); claim_and_release(1,4,41);
            // Natural overflow of official 4096x32 + 16x128 FIFOs.
            a=abort_count; p=pub_count; stall_w=1; stall_b=1;
            frame(10,PIXELS); repeat(20)@(negedge clk);
            if(!abort_req||abort_count!=a||bstate0!==1||flush) $fatal(1,"overflow retirement violation");
            stall_w=0; wait(bv); drop_frame(11);
            if(abort_count!=a||bstate0!==1||flush) $fatal(1,"overflow/B freed early");
            stall_b=0; wait(abort_count==a+1); quiet();
            if(pub_count!=p||bstate0!==0||diag[31:16]==0) $fatal(1,"overflow published");
            frame(12,PIXELS); finish_good(5); claim_and_release(0,5,41);
            // Full tag payload accepted, but its B held for another full frame.
            stall_tag_b=1; p=pub_count;
            frame(13,PIXELS); wait(cur_tag&&bv); drop_frame(14);
            ack=3; repeat(20)@(negedge clk); ack=0;
            if(pub_count!=p||bstate1!==1||iv||hv||aborted) $fatal(1,"tag B published early");
            stall_tag_b=0; finish_good(6); claim_and_release(1,6,41);
            a=abort_count; p=pub_count; tag_error=1;
            frame(15,PIXELS); wait(abort_count==a+1); quiet(); tag_error=0;
            if(pub_count!=p||bstate0!==0) $fatal(1,"bad tag published");
            frame(16,PIXELS); finish_good(7); claim_and_release(0,7,41);
            a=abort_count; p=pub_count; data_error=1;
            frame(17,PIXELS); wait(abort_count==a+1); quiet(); data_error=0;
            if(pub_count!=p||bstate1!==0) $fatal(1,"bad payload published");
            frame(18,PIXELS); finish_good(8); claim_and_release(1,8,41);
            // Reset after real AW acceptance. Reset DMA AND memory bus model.
            stall_w=1; frame(19,128); wait(bus_active); repeat(10)@(negedge clk);
            rst=1; repeat(8)@(negedge clk); rst=0; stall_w=0; quiet();
            drop_frame(20); arm(0,0); arm(42,1);
            frame(21,PIXELS); finish_good(1); claim(0,0,1,42); claim(1,0,1,42);
            release_one(0,4,0,1,41,{32'd41,32'd1},0);
            release_one(1,4,0,1,41,{32'd41,32'd1},0);
            release_both(0,1,42); arm(42,0); arm(0,0); arm(43,1);
            frame(22,PIXELS); finish_good(1); claim_and_release(0,1,43);
            // Rollover acceleration: deposit near-limit counters, no RTL change.
            quiet(); @(negedge clk);
            manager.next_sequence=32'hffffffff;
            camera.ov5640_ddr_w_ctrl.frame_cnt=32'hfffffffe;
            camera.ov5640_ddr_w_ctrl.last_cnt=32'hfffffffe;
            $fdisplay(trace,"Q 4294967295");
            frame(23,PIXELS); finish_good(32'hffffffff);
            if(armed) $fatal(1,"sequence wrap did not disarm"); drop_frame(24);
            claim_and_release(1,32'hffffffff,43); arm(44,1);
            frame(25,PIXELS); finish_good(1); claim(0,0,1,44); claim(1,0,1,44);
            release_parallel(0,1,44,1);
            release_parallel(0,1,44,0);
            if(bstate0!==0) $fatal(1,"parallel release did not free");
        end
        quiet();
        if(bus_active||bv||av||wv||iv||hv||bstate0||bstate1) $fatal(1,"final ownership not drained");
        $fdisplay(trace,"Z %0d %0d %0d %0d %0d",checks,aw_count,b_count,w_count,abort_count);
        $fclose(trace);
        $display("CAPTURE_LEASE_PASS words=%0d host=%0d bad=%0d checks=%0d AW=%0d B=%0d W=%0d abort=%0d",WORDS,HOST_REQUIRED,BAD_CFG,checks,aw_count,b_count,w_count,abort_count);
        $finish;
    end
    initial begin #300000000; $fatal(1,"timeout state=%0d pub=%0d abort=%0d",state,pub_count,abort_count); end
endmodule
