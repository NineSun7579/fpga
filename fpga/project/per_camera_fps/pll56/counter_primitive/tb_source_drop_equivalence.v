`timescale 1ns/1ps
// Identical FIFO interface model isolates the diagnostic counter experiment.
// FIFO RTL is unchanged and is not revalidated by this test.
module ov5640_cdc_fifo (
    input wr_clk, wr_rst, wr_en, input [23:0] wr_data,
    output wr_full, input rd_clk, rd_en, rd_rst,
    output [23:0] rd_data, output rd_empty, almost_full, almost_empty
);
    assign wr_full = tb_source_drop_equivalence.full_control;
    assign rd_empty = tb_source_drop_equivalence.empty_control;
    assign rd_data = 24'h123456;
    assign almost_full = wr_full;
    assign almost_empty = rd_empty;
endmodule

module tb_source_drop_equivalence;
    GTP_GRS GRS_INST (.GRS_N(1'b1));
    reg cam_clk=0, video_clk=0;
    always #8.9285 cam_clk=~cam_clk;
    always #3.8095 video_clk=~video_clk;
    reg cam_rst=1, video_rst=1;
    reg s_valid=0, s_vsync=0, s_hsync=0;
    reg [23:0] s_data=0;
    reg full_control=0, empty_control=1;
    wire [31:0] ri,ro,rd,rs,ci,co,cd,cs;
    wire [23:0] rdata,cdata;
    wire rv,rh,rvs,cv,ch,cvs;
    integer cam_edges=0, video_edges=0, n;
    reg checking=1;
    ov5640_cdc_reference reference (
        .cam_clk(cam_clk),.cam_rst(cam_rst),.s_data(s_data),.s_valid(s_valid),
        .s_hsync(s_hsync),.s_vsync(s_vsync),.video_clk(video_clk),.video_rst(video_rst),
        .dbg_cdc_input(ri),.dbg_cdc_output(ro),.dbg_cdc_drop(rd),.dbg_cdc_seq(rs),
        .video_data(rdata),.video_valid(rv),.video_hsync(rh),.video_vsync(rvs)
    );
    ov5640_cdc candidate (
        .cam_clk(cam_clk),.cam_rst(cam_rst),.s_data(s_data),.s_valid(s_valid),
        .s_hsync(s_hsync),.s_vsync(s_vsync),.video_clk(video_clk),.video_rst(video_rst),
        .dbg_cdc_input(ci),.dbg_cdc_output(co),.dbg_cdc_drop(cd),.dbg_cdc_seq(cs),
        .video_data(cdata),.video_valid(cv),.video_hsync(ch),.video_vsync(cvs)
    );
    task compare;
        begin
            if (checking && (
                {reference.src_drop,reference.src_count,reference.src_seq,
                 reference.src_snapshot,reference.src_toggle,reference.src_vs_q} !==
                {candidate.src_drop,candidate.src_count,candidate.src_seq,
                 candidate.src_snapshot,candidate.src_toggle,candidate.src_vs_q}
                || {reference.snapshot_s1,reference.snapshot_s2,reference.toggle_sync,
                    reference.toggle_seen,reference.out_count,reference.out_snapshot} !==
                   {candidate.snapshot_s1,candidate.snapshot_s2,candidate.toggle_sync,
                    candidate.toggle_seen,candidate.out_count,candidate.out_snapshot}
                || {ri,ro,rd,rs,rdata,rv,rh,rvs} !== {ci,co,cd,cs,cdata,cv,ch,cvs})) begin
                $display("FAIL mismatch time=%t cam_edges=%d",$time,cam_edges);
                $fatal(1);
            end
        end
    endtask
    always @(posedge cam_clk) begin #0.1; cam_edges=cam_edges+1; compare; end
    always @(posedge video_clk) begin #0.1; video_edges=video_edges+1; compare; end
    always @(posedge cam_rst) begin #0.1; compare; end
    task step;
        input valid, vs, full, empty;
        begin
            @(negedge cam_clk);
            s_valid=valid; s_vsync=vs; full_control=full; empty_control=empty;
            s_hsync=valid; s_data=s_data+1;
            @(posedge cam_clk); #0.2;
        end
    endtask
    initial begin
        repeat(8) @(negedge cam_clk);
        cam_rst=0; video_rst=0;
        // Frame rise coincident with valid and FIFO-full is a load of one,
        // while the snapshot contains the previous frame's count.
        step(1,1,1,0);
        if(candidate.src_drop !== 1 || candidate.src_snapshot[63:32] !== 0) $fatal(1);
        step(1,1,0,0); step(1,0,1,0); step(0,0,1,1);
        // Full 640x480 offered frame, with deterministic FIFO pressure and gaps.
        step(1,1,0,0);
        for(n=1;n<307200;n=n+1) begin
            step(1,0,((n%97)<13),((n%37)<2));
            if ((n%4096)==0) step(0,0,1,1);
        end
        repeat(100) step(0,0,0,1);
        step(0,1,0,1);
        if(candidate.src_snapshot[31:0] !== 307200) $fatal(1);
        repeat(100) step(0,0,0,1);
        // Seed both original and extracted register identically near overflow.
        @(negedge cam_clk); checking=0;
        force reference.src_drop=32'hfffffffc;
        $deposit(candidate.u_src_drop.bits[0].ff.qout, 1'b0);
        $deposit(candidate.u_src_drop.bits[1].ff.qout, 1'b0);
        $deposit(candidate.u_src_drop.bits[2].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[3].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[4].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[5].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[6].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[7].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[8].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[9].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[10].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[11].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[12].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[13].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[14].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[15].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[16].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[17].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[18].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[19].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[20].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[21].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[22].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[23].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[24].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[25].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[26].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[27].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[28].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[29].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[30].ff.qout, 1'b1);
        $deposit(candidate.u_src_drop.bits[31].ff.qout, 1'b1);
        #0.1;
        release reference.src_drop;
        checking=1;
        repeat(8) step(1,0,1,0);
        if(candidate.src_drop !== 4) $fatal(1);
        step(1,1,1,0);
        if(candidate.src_drop !== 1 || candidate.src_snapshot[63:32] !== 4) $fatal(1);
        // Asynchronous source reset, independent destination reset, recovery.
        #1.17; cam_rst=1; #0.3; compare;
        repeat(5) @(negedge cam_clk);
        cam_rst=0;
        step(1,1,1,0); step(1,0,1,0);
        #1.23; video_rst=1;
        repeat(8) @(negedge video_clk);
        video_rst=0;
        repeat(100) step(0,0,0,1);
        // Short/restarted frames, sustained VSYNC, mixed valid/full boundaries.
        for(n=0;n<20000;n=n+1)
            step((n%7)!=0,(n%113)<5,(n%17)<8,(n%19)<6);
        repeat(100) step(0,0,0,1);
        $display("PASS SOURCE_DROP_EQUIVALENCE cam_edges=%d video_edges=%d full_frame=307200 wrap=PASS async_reset=PASS snapshot=PASS",cam_edges,video_edges);
        $finish;
    end
endmodule
