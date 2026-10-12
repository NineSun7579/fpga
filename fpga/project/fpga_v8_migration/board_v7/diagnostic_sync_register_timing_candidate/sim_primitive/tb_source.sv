`timescale 1ns/1ps
module tb_v7_sfd_candidate;
 GTP_GRS GRS_INST (.GRS_N(1'b1));
    reg cam_clk=0,host_clk=0;
    always #5 cam_clk=~cam_clk;
    always #7 host_clk=~host_clk;
    reg cam_reset=1,host_reset=1;
    reg h=0,v=0;
    wire cv,cs,ch;
    wire [15:0] data_unused;
    cmos_capture #(.DATA_WIDTH(16),.DELAY(2)) capture(
        .rst_n(!cam_reset),.cam_pclk(cam_clk),.cam_vsync(v),.cam_href(h),
        .cam_data(8'd0),.cmos_frame_vsync(cs),.cmos_frame_href(ch),
        .cmos_frame_valid(cv),.cmos_frame_data(data_unused));
    // Exact binding sampling point, including its unreset falling-edge stage.
    reg cv_r,cs_r;
    always @(negedge cam_clk) begin cv_r<=cv;cs_r<=cs;end
    reg inject=0, inject_valid=0;
    wire observed_valid=inject ? inject_valid : cv_r;
    reg rd=0,acq=0,rel=0;
    reg [4:0] addr=0;
    wire [31:0] rdata;
    wire rv,re,sv,av,ov;
    v7_sfd_candidate dut(cam_clk,cam_reset,host_clk,host_reset,
        v,h,h,cs_r,observed_valid,rd,acq,rel,addr,rdata,rv,re,sv,av,ov);

    wire [31:0] ref_data;
    wire ref_rv,ref_re,ref_sv,ref_av,ref_ov;
    dsr_baseline_source ref_dut(cam_clk,cam_reset,host_clk,host_reset,
        v,h,h,cs_r,observed_valid,rd,acq,rel,addr,ref_data,ref_rv,ref_re,ref_sv,ref_av,ref_ov);
    integer compare_cam=0,compare_host=0,compare_async=0;
    task compare_all;
      begin
        if({rdata,rv,re,sv,av,ov} !== {ref_data,ref_rv,ref_re,ref_sv,ref_av,ref_ov})
          $fatal(1,"FAIL source complete outputs t=%0t",$time);
        if({dut.cr,dut.hr,dut.ack_sync,dut.req_sync,dut.overrun_sync,
            dut.request,dut.ack,dut.mailbox,dut.host_bank,dut.seq_q,
            dut.bytes_q,dut.aligned_q,dut.native_q,dut.overlap_q,dut.raw_overlap_q,
            dut.segments_q,dut.odd_q,dut.gap_q} !==
           {ref_dut.cr,ref_dut.hr,ref_dut.ack_sync,ref_dut.req_sync,ref_dut.overrun_sync,
            ref_dut.request,ref_dut.ack,ref_dut.mailbox,ref_dut.host_bank,ref_dut.seq_q,
            ref_dut.bytes_q,ref_dut.aligned_q,ref_dut.native_q,ref_dut.overlap_q,ref_dut.raw_overlap_q,
            ref_dut.segments_q,ref_dut.odd_q,ref_dut.gap_q})
          $fatal(1,"FAIL source stages mailbox handshake counters t=%0t",$time);
      end
    endtask
    always @(posedge cam_clk) begin #0.002; compare_all(); compare_cam++; end
    always @(posedge host_clk) begin #0.002; compare_all(); compare_host++; end
    always @(posedge cam_reset or posedge host_reset) begin #0.002; compare_all(); compare_async++; end
    integer errors=0,checks=0;
    reg unit_rst=1,unit_inc=0,unit_clear=0,unit_seed=0;
    wire [7:0] unit_q,unit_next;
    v7_sfd_counter #(.W(8)) counter_unit(cam_clk,unit_rst,unit_clear,unit_seed,unit_inc,unit_q,unit_next);
    integer u,expected_unit=0;
    initial begin
        repeat(3) @(negedge cam_clk);unit_rst=0;
        for(u=0;u<1200;u++) begin
            @(negedge cam_clk);unit_inc=(u%5!=0);
            expected_unit=(expected_unit+unit_inc)%256;
            @(posedge cam_clk);#1;check(unit_q==expected_unit,"prefix increment/hold/wrap");
        end
        @(negedge cam_clk);unit_clear=1;unit_seed=1;
        @(posedge cam_clk);#1;check(unit_q==1,"prefix clear with boundary seed");
        @(negedge cam_clk);unit_clear=0;unit_inc=1;
        @(posedge cam_clk);#1;check(unit_q==2,"prefix after seeded clear");
        $display("PASS prefix_counter_wrap_hold_seed");
    end
    reg [31:0] words[0:15];
    reg [31:0] held_words[0:15];
    task check(input bit ok,input string msg);
        begin checks++;if(!ok) begin errors++;$display("FAIL %s t=%0t",msg,$time);end end
    endtask
    task tick(input bit hh,input bit vv,input integer n);
        repeat(n) begin @(negedge cam_clk);#1;h=hh;v=vv;@(posedge cam_clk);#1;end
    endtask
    task marker;
        begin tick(0,1,4);tick(0,0,8);end
    endtask
    task reset_all;
        begin
            @(negedge cam_clk);cam_reset=1;host_reset=1;h=0;v=0;inject=0;
            rd=0;acq=0;rel=0;repeat(8) @(negedge cam_clk);
            cam_reset=0;repeat(5) @(negedge host_clk);host_reset=0;
            tick(0,0,8);
            repeat(11) marker();
            check(!sv,"warmup produces no partial snapshot");
        end
    endtask
    task read_one(input integer a,output reg [31:0] d);
        begin
            @(negedge host_clk);addr=a;rd=1;
            @(posedge host_clk);#1;d=rdata;check(rv,"read response");
            @(negedge host_clk);rd=0;
        end
    endtask
    task get_snapshot;
        integer timeout_n,i;
        begin
            timeout_n=0;
            while(!sv && !av && timeout_n<100) begin @(posedge host_clk);#1;timeout_n++;end
            if(!sv && av) begin
                @(negedge host_clk);acq=1;@(negedge host_clk);acq=0;
            end
            check(sv,"snapshot available");
            for(i=0;i<16;i++) begin read_one(i,words[i]);check(!re,"leased read has no error");end
            check(words[15]==32'h53464401,"format magic");
        end
    endtask
    task release_snapshot;
        begin
            @(negedge host_clk);rel=1;@(negedge host_clk);rel=0;
            repeat(8) @(posedge cam_clk);
        end
    endtask
    task expect_counts(input integer b,s,o,a,n,g);
        begin
            get_snapshot();
            check(words[1]==b,$sformatf("bytes actual=%0d expected=%0d",words[1],b));
            check(words[2]==s,"HREF fragments");check(words[3]==o,"odd tails");
            check(words[4]==a,$sformatf("aligned valid actual=%0d expected=%0d",words[4],a));
            check(words[5]==n,"native valid");check(words[7][15:0]==g,"tail gap");
            check(!words[7][23],"frame count trustworthy");
            check(words[1]-words[3]==2*words[4],"byte/pair conservation");
            check($signed(words[5])-$signed(words[4])==
                integer'(words[12][3])-integer'(words[12][2]),"native/aligned endpoint identity");
        end
    endtask
    integer i,j,k,deficit;
    reg [31:0] saved,again;
    // Independent edge scoreboard, native capture window semantics.
    integer ref_bytes=0,ref_aligned=0,ref_native=0,ref_seg=0,ref_odd=0;
    reg [1:0] rhd=0,rvd=0;
    reg ref_vd=0,ref_vq=0,ref_hq=0,ref_parity=0,ref_arm=0;
    always @(posedge cam_clk) begin
        if(dut.rst_c) begin
            rhd=0;rvd=0;ref_vd=0;ref_vq=0;ref_hq=0;ref_parity=0;ref_arm=0;
            ref_bytes=0;ref_aligned=0;ref_native=0;ref_seg=0;ref_odd=0;
        end else begin
            if(cs_r && !ref_vq) begin
                if(ref_arm && !dut.busy) begin
                    // Include a segment ending exactly at VSYNC.
                    if(ref_hq && ref_parity) ref_odd++;
                    #0.001;
                    check(dut.mailbox[32+:32]==ref_bytes,"scoreboard bytes");
                    check(dut.mailbox[64+:32]==ref_seg,"scoreboard segments");
                    check(dut.mailbox[96+:32]==ref_odd,"scoreboard odd");
                    check(dut.mailbox[128+:32]==ref_aligned,"scoreboard aligned");
                    check(dut.mailbox[160+:32]==ref_native,"scoreboard native");
                end
                ref_bytes=0;ref_aligned=0;ref_native=0;ref_seg=0;ref_odd=0;
                ref_parity=0;ref_hq=0;ref_arm=1;
            end
            if(ref_arm) begin
                if(rhd[1]) begin ref_bytes++;ref_parity=~ref_parity;end
                if(ref_vd) ref_aligned++;
                if(observed_valid) ref_native++;
                if(rhd[1] && !ref_hq) ref_seg++;
                if(!rhd[1] && ref_hq) begin
                    if(ref_parity) ref_odd++;
                    ref_parity=0;
                end
            end
            ref_hq=rhd[1];ref_vq=cs_r;ref_vd=observed_valid;
            rhd={rhd[0],h};rvd={rvd[0],v};
        end
    end
    initial begin
        reset_all();
        for(i=0;i<480;i++) begin tick(1,0,1280);if(i<479) tick(0,0,16);end
        tick(0,0,20);marker();expect_counts(614400,480,0,307200,307200,20);
        $display("PASS normal_640x480");release_snapshot();

        // Same byte total, different segmentation. These reproduce numerical
        // source deficits, not a claim that the board has such HREF waveforms.
        for(k=0;k<3;k++) begin
            case(k) 0:deficit=1;1:deficit=2;2:deficit=7;endcase
            reset_all();
            for(i=0;i<480;i++) begin
                if(i<deficit) begin tick(1,0,639);tick(0,0,1);tick(1,0,641);end
                else tick(1,0,1280);
                if(i<479) tick(0,0,16);
            end
            tick(0,0,20);marker();
            expect_counts(614400,480+deficit,2*deficit,307200-deficit,307200-deficit,20);
            $display("PASS full_size_odd_segments source=%0d",307200-deficit);
            release_snapshot();
        end

        reset_all();tick(1,0,7);tick(0,0,1);tick(1,0,9);
        tick(0,0,5);marker();expect_counts(16,2,2,7,7,5);
        $display("PASS one_cycle_low_two_odd_segments");release_snapshot();

        reset_all();tick(1,0,1278);tick(0,0,6);marker();
        expect_counts(1278,1,0,639,639,6);
        $display("PASS missing_two_bytes");release_snapshot();

        reset_all();tick(1,0,7);marker();expect_counts(7,1,1,3,3,0);
        $display("PASS odd_tail_closed_on_boundary_zero_blank");release_snapshot();
        marker();get_snapshot();
        check(words[1]==0 && words[2]==0 && words[4]==0,"empty frame counts");
        check(!words[7][18] && words[7][15:0]==0,"empty frame gap marked unavailable");
        $display("PASS empty_frame");release_snapshot();

        reset_all();tick(1,0,8);tick(0,0,70000);marker();
        expect_counts(8,1,0,4,4,65535);check(words[7][19],"gap saturated flag");
        $display("PASS saturated_gap");release_snapshot();

        // Source-side mailbox must not change while host reads, even when many
        // frames arrive, and dropped frames must still update previous metrics.
        reset_all();tick(1,0,8);tick(0,0,3);marker();get_snapshot();saved=words[0];
        for(j=0;j<16;j++) held_words[j]=words[j];
        for(i=0;i<5;i++) begin tick(1,0,10+i*2);tick(0,0,2);marker();end
        get_snapshot();check(words[0]==saved && words[1]==8,"lease stays atomic under overrun");
        for(j=0;j<16;j++) check(words[j]==held_words[j],"every host word immutable while leased");
        check(ov,"overrun visible while original lease held");
        release_snapshot();tick(1,0,24);tick(0,0,2);marker();get_snapshot();
        check(words[0]==7,"sequence exposes five skipped frames");
        check(words[8]==18 && words[9]==9 && words[10]==9,"previous frame includes dropped snapshot");
        check(words[1]==24 && words[4]==12,"new lease complete");
        $display("PASS overrun_atomic_previous");release_snapshot();

        // Deliberate RTL boundary stress: a four-byte fragment straddles raw
        // VSYNC (one before, three after). Its first pair ends ON the marker.
        // Native valid advances into preceding window; aligned valid remains
        // with its final byte. Clipped-segment flag prohibits naive B/2 claims.
        reset_all();tick(1,0,8);tick(0,0,2);tick(1,0,1);
        tick(1,1,3);tick(0,1,2);tick(0,0,8);get_snapshot();
        check(words[1]==9 && words[4]==4 && words[5]==5,"boundary window displacement");
        check(words[7][20],"crossing HREF segment flagged");
        check(words[12][3]==1,"end aligned token");release_snapshot();
        tick(1,0,6);tick(0,0,3);marker();get_snapshot();
        check(words[1]==9 && words[4]==5 && words[5]==4,"adjacent window compensates");
        check(words[6]>=1,"VSYNC high overlap count");
        check(words[14]==3,"raw bytes overlapping VSYNC");
        check(words[4]+words[9]==words[5]+words[10],"two-frame conservation");
        $display("PASS boundary_adjacent_conservation");release_snapshot();

        // Explicit capture-valid on marker, separate from raw HREF: verify
        // overlap is counted and the measurement does not manufacture bytes.
        reset_all();inject=1;inject_valid=1;marker();get_snapshot();
        check(words[12][1],"closing boundary native valid");release_snapshot();
        marker();get_snapshot();check(words[6]>0,"injected VSYNC-valid overlap");
        $display("PASS valid_boundary_injection");

        // Independent host reset cancels a busy lease and clears the CDC phase.
        @(negedge host_clk);host_reset=1;repeat(4) @(negedge host_clk);
        host_reset=0;tick(0,0,10);check(!sv && !ov,"host reset cancels session");
        inject=0;marker();tick(1,0,8);tick(0,0,2);marker();
        check(!sv && av,"new snapshot requires fresh acquire after reset");
        read_one(1,again);check(re && again==0,"no implicit lease after reset");
        expect_counts(8,1,0,4,4,2);
        // Camera-only reset while host holds a lease; no stale replay allowed.
        @(negedge cam_clk);cam_reset=1;repeat(5) @(negedge cam_clk);
        cam_reset=0;tick(0,0,10);check(!sv && !ov,"camera reset cancels session");
        repeat(11) marker();tick(1,0,6);tick(0,0,4);marker();expect_counts(6,1,0,3,3,4);
        $display("PASS independent_domain_resets");
        $display("SFD_DONE checks=%0d errors=%0d",checks,errors);
        if(errors==0) $display("SFD_ALL_PASS");
        $display("DSR_SOURCE_COMPARE_PASS cam=%0d host=%0d async=%0d",compare_cam,compare_host,compare_async);
        $finish;
    end
    initial begin #60000000;$fatal(1,"watchdog");end
endmodule
