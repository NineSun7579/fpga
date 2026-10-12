`timescale 1ns/1ps
// Single-beat, 16-byte-aligned AXI128 accesses through the actual stage chain.
// LEN=0, SIZE=4: no burst behavior is assumed by this regression.
module tb_motion_axi_bridge;
    reg clk=0; always #5 clk=~clk;
    reg rst=1;
    reg success=0;
    reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
    reg [31:0] awaddr=0,araddr=0;
    reg [127:0] wdata=0;
    reg [15:0] wstrb=0;
    reg [3:0] awid=0,arid=0;
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [3:0] bid,rid;
    wire [127:0] rdata;
    wire [1:0] bresp,rresp;
    wire lav,lwv,lbv,lbr,larv,larr,lrv,lrr,lawr,lwr;
    wire [31:0] laa,lwd,lara,lrd;
    wire [3:0] lws;
    wire [1:0] lbp,lrp;
    wire [4:0] mav,mwv,mbv,mbr,marv,marr,mrv,mrr,mawr,mwr;
    wire [31:0] maa[0:4],mwd[0:4],mara[0:4],mrd[0:4];
    wire [3:0] mws[0:4];
    wire [1:0] mbp[0:4],mrp[0:4];
    reg [1919:0] records=0;
    reg publish=0;
    integer epoch=0;
    integer writes[0:4],reads[0:4];
    integer write_total=0,read_total=0,stall_cycles=0;
    integer c,j,k,before_count;
    reg [31:0] expected[0:9];

    axi_to_axi_lite #(.ADDR_WIDTH(32),.DATA_WIDTH(32),.AXI_ID_LEN(4),.AXI_DATA_LEN(128)) bridge (
        .axi_clk(clk),.axi_rst(rst),
        .s_axi_awid(awid),.s_axi_awaddr(awaddr),.s_axi_awlen(8'd0),
        .s_axi_awsize(3'd4),.s_axi_awburst(2'b01),.s_axi_awlock(2'd0),
        .s_axi_awcache(4'd0),.s_axi_awprot(3'd0),.s_axi_awqos(4'd0),.s_axi_awregion(4'd0),
        .s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wlast(1'b1),
        .s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bid(bid),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_arid(arid),.s_axi_araddr(araddr),.s_axi_arlen(8'd0),
        .s_axi_arsize(3'd4),.s_axi_arburst(2'b01),.s_axi_arlock(2'd0),
        .s_axi_arcache(4'd0),.s_axi_arprot(3'd0),.s_axi_arqos(4'd0),.s_axi_arregion(4'd0),
        .s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rid(rid),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rlast(rlast),
        .s_axi_rvalid(rvalid),.s_axi_rready(rready),
        .m_axil_awaddr(laa),.m_axil_awvalid(lav),.m_axil_awready(lawr),
        .m_axil_wdata(lwd),.m_axil_wstrb(lws),.m_axil_wvalid(lwv),.m_axil_wready(lwr),
        .m_axil_bresp(lbp),.m_axil_bvalid(lbv),.m_axil_bready(lbr),
        .m_axil_araddr(lara),.m_axil_arvalid(larv),.m_axil_arready(larr),
        .m_axil_rdata(lrd),.m_axil_rresp(lrp),.m_axil_rvalid(lrv),.m_axil_rready(lrr)
    );
    ovreg_axil_decode dec (
        .clk(clk),.rst(rst),
        .s_awvalid(lav),.s_awready(lawr),.s_awaddr(laa),
        .s_wvalid(lwv),.s_wready(lwr),.s_wdata(lwd),.s_wstrb(lws),
        .s_bvalid(lbv),.s_bready(lbr),.s_bresp(lbp),
        .s_arvalid(larv),.s_arready(larr),.s_araddr(lara),
        .s_rvalid(lrv),.s_rready(lrr),.s_rdata(lrd),.s_rresp(lrp),
        .m0_awvalid(mav[0]),.m0_awready(mawr[0]),.m0_awaddr(maa[0]),
        .m0_wvalid(mwv[0]),.m0_wready(mwr[0]),.m0_wdata(mwd[0]),.m0_wstrb(mws[0]),
        .m0_bvalid(mbv[0]),.m0_bready(mbr[0]),.m0_bresp(mbp[0]),
        .m0_arvalid(marv[0]),.m0_arready(marr[0]),.m0_araddr(mara[0]),
        .m0_rvalid(mrv[0]),.m0_rready(mrr[0]),.m0_rdata(mrd[0]),.m0_rresp(mrp[0]),
        .m1_awvalid(mav[1]),.m1_awready(mawr[1]),.m1_awaddr(maa[1]),
        .m1_wvalid(mwv[1]),.m1_wready(mwr[1]),.m1_wdata(mwd[1]),.m1_wstrb(mws[1]),
        .m1_bvalid(mbv[1]),.m1_bready(mbr[1]),.m1_bresp(mbp[1]),
        .m1_arvalid(marv[1]),.m1_arready(marr[1]),.m1_araddr(mara[1]),
        .m1_rvalid(mrv[1]),.m1_rready(mrr[1]),.m1_rdata(mrd[1]),.m1_rresp(mrp[1]),
        .m2_awvalid(mav[2]),.m2_awready(mawr[2]),.m2_awaddr(maa[2]),
        .m2_wvalid(mwv[2]),.m2_wready(mwr[2]),.m2_wdata(mwd[2]),.m2_wstrb(mws[2]),
        .m2_bvalid(mbv[2]),.m2_bready(mbr[2]),.m2_bresp(mbp[2]),
        .m2_arvalid(marv[2]),.m2_arready(marr[2]),.m2_araddr(mara[2]),
        .m2_rvalid(mrv[2]),.m2_rready(mrr[2]),.m2_rdata(mrd[2]),.m2_rresp(mrp[2]),
        .m3_awvalid(mav[3]),.m3_awready(mawr[3]),.m3_awaddr(maa[3]),
        .m3_wvalid(mwv[3]),.m3_wready(mwr[3]),.m3_wdata(mwd[3]),.m3_wstrb(mws[3]),
        .m3_bvalid(mbv[3]),.m3_bready(mbr[3]),.m3_bresp(mbp[3]),
        .m3_arvalid(marv[3]),.m3_arready(marr[3]),.m3_araddr(mara[3]),
        .m3_rvalid(mrv[3]),.m3_rready(mrr[3]),.m3_rdata(mrd[3]),.m3_rresp(mrp[3]),
        .m4_awvalid(mav[4]),.m4_awready(mawr[4]),.m4_awaddr(maa[4]),
        .m4_wvalid(mwv[4]),.m4_wready(mwr[4]),.m4_wdata(mwd[4]),.m4_wstrb(mws[4]),
        .m4_bvalid(mbv[4]),.m4_bready(mbr[4]),.m4_bresp(mbp[4]),
        .m4_arvalid(marv[4]),.m4_arready(marr[4]),.m4_araddr(mara[4]),
        .m4_rvalid(mrv[4]),.m4_rready(mrr[4]),.m4_rdata(mrd[4]),.m4_rresp(mrp[4])
    );
    prep_regs #(.SFP_DIAG_EN(1)) prep (
        .clk(clk),.rst_n(!rst),.motion_records(records),
        .prep_bypass(),.prep_mode(),.prep_img_width(),.prep_thr_sat(),
        .prep_thr_hue(),.prep_thr_val(),.prep_thr_low(),.prep_thr_edge(),
        .prep_lane_roi_top(),.prep_lane_roi_bot(),.prep_lane_row_thr(),.prep_lane_dash_thr(),
        .inj_addr(),.inj_len(),.inj_frame_id(),.inj_start(),.inj_done_clr(),
        .btn_sticky(),.btn_sticky_clr(),.led_ctrl(),
        .ts_value0(),.ts_value1(),.ts_value2(),.ts_value3(),
        .s_axi_awvalid(mav[1]),.s_axi_awready(mawr[1]),.s_axi_awaddr(maa[1]),
        .s_axi_wvalid(mwv[1]),.s_axi_wready(mwr[1]),.s_axi_wdata(mwd[1]),.s_axi_wstrb(mws[1]),
        .s_axi_bvalid(mbv[1]),.s_axi_bready(mbr[1]),.s_axi_bresp(mbp[1]),
        .s_axi_arvalid(marv[1]),.s_axi_arready(marr[1]),.s_axi_araddr(mara[1]),
        .s_axi_rvalid(mrv[1]),.s_axi_rready(mrr[1]),.s_axi_rdata(mrd[1]),.s_axi_rresp(mrp[1]),
        .inj_busy(1'b0),.inj_done(1'b0),.inj_done_fid(16'd0),
        .pipe_frame_sync(1'b0),.pipe_fifo_afull(1'b0),.npu_busy(1'b0),.out_frame_cnt(8'd0),
        .btn_toggle_evt(4'd0),.btn_level_sync(4'd0),
        .lane_left_type(2'd0),.lane_right_type(2'd0),.lane_left_valid(1'b0),
        .lane_right_valid(1'b0),.lane_frame_upd(1'b0),
        .ts_cap_pulse(1'b0),.ts_prep_pulse(1'b0),.ts_npu_pulse(1'b0),.ts_dma_pulse(1'b0),
        .dbg_pp_beats(32'h100180),.dbg_prep_aw(32'h100184),
        .dbg_prep_w(32'h100188),.dbg_prep_b(32'h10018c),
        .sfp_diag_status(32'h12345678),.sfp_diag_fault5(32'h23456789),
        .sfp_diag_fault6(32'h3456789a),.sfp_diag_pixels5(32'h456789ab),
        .sfp_diag_pixels6(32'h56789abc),.sfp_diag_states(32'h6789abcd),
        .sfp_diag_rejects(32'h789abcde)
    );
    genvar g;
    generate for(g=0;g<5;g=g+1) begin: endpoints
        if(g!=1) begin
            motion_bridge_camera_stub #(.ID(g)) cam (
                .clk(clk),.rst(rst),.awvalid(mav[g]),.awready(mawr[g]),
                .wvalid(mwv[g]),.wready(mwr[g]),.bvalid(mbv[g]),.bready(mbr[g]),.bresp(mbp[g]),
                .arvalid(marv[g]),.arready(marr[g]),.araddr(mara[g]),
                .rvalid(mrv[g]),.rready(mrr[g]),.rdata(mrd[g]),.rresp(mrp[g])
            );
        end
        always @(posedge clk) begin
            if(rst) begin writes[g]<=0;reads[g]<=0;end
            else begin
                if(mav[g] && mawr[g]) writes[g]<=writes[g]+1;
                if(marv[g] && marr[g]) reads[g]<=reads[g]+1;
            end
        end
    end endgenerate

    // Unique, ABI-shaped publications for every camera and bitmap word.
    function automatic [31:0] publication(input integer e,input integer cam,input integer word_no);
        case(word_no)
            0: publication=32'h12340000+(e<<8)+cam;
            1: publication=cam & 7;
            2: publication=((4800+e+cam)<<8)|(192-cam);
            3: publication=32'h0000b0f0;
            default: publication=32'h13579bdf ^ (e<<12) ^ (cam<<24) ^ (word_no<<16);
        endcase
    endfunction
    integer pc,pw;
    always @(negedge clk) if(publish) begin
        epoch=epoch+1;
        for(pc=0;pc<6;pc=pc+1)
            for(pw=0;pw<10;pw=pw+1)
                records[pc*320+pw*32+:32]=publication(epoch,pc,pw);
    end
    // Assert full addresses on the Lite side, not just low-page register values.
    always @(posedge clk) if(!rst) begin
        if(awvalid && awready && laa!==awaddr) $fatal(1,"AW address truncated");
        if(arvalid && arready && lara!==araddr) $fatal(1,"AR address truncated");
        if(wvalid && wready && (lwd!==wdata[31:0] || lws!==wstrb[3:0]))
            $fatal(1,"bridge low-word/strobes mismatch");
    end

    task automatic write_reg(input [31:0] address,input [31:0] data,input [15:0] strobes);
        reg [3:0] txn_id;
        begin
            if(address[3:0]!=0) $fatal(1,"unaligned write BFM");
            txn_id=(write_total+1)&15;
            @(negedge clk); awaddr=address;awid=txn_id;awvalid=1;
            do @(posedge clk); while(!awready);
            @(negedge clk);awvalid=0;awaddr=32'hdead0600;awid=~txn_id;
            repeat(3) @(negedge clk);
            // Deliberately nonzero upper lanes; only low word may be used.
            wdata={32'h80000509,32'hfeedface,32'hdeadbeef,data};wstrb=strobes;wvalid=1;
            do @(posedge clk); while(!wready);
            @(negedge clk);wvalid=0;wdata='1;wstrb=0;
            while(!bvalid) @(negedge clk);
            repeat(4) begin
                @(negedge clk);
                if(!bvalid || bresp!==0 || bid!==txn_id) $fatal(1,"B unstable/error addr=%h id=%h expected=%h",address,bid,txn_id);
            end
            bready=1;@(negedge clk);bready=0;
            write_total=write_total+1;
        end
    endtask
    task automatic read_reg(input [31:0] address,input [31:0] wanted);
        reg [3:0] txn_id;
        reg [127:0] held;
        begin
            if(address[3:0]!=0) $fatal(1,"unaligned read BFM");
            txn_id=(read_total+3)&15;
            @(negedge clk);araddr=address;arid=txn_id;arvalid=1;
            do @(posedge clk); while(!arready);
            @(negedge clk);arvalid=0;araddr=32'hdead0600;arid=~txn_id;
            while(!rvalid) @(negedge clk);
            held=rdata;
            repeat(5) begin
                @(negedge clk);stall_cycles=stall_cycles+1;
                if(!rvalid || rdata!==held || rresp!==0 || rid!==txn_id || rlast!==1)
                    $fatal(1,"R unstable/error addr=%h",address);
            end
            if(held!=={96'd0,wanted}) $fatal(1,"read %h got %032h expected %032h",address,held,{96'd0,wanted});
            rready=1;@(negedge clk);rready=0;
            read_total=read_total+1;
        end
    endtask
    task automatic camera_route(input [31:0] address,input integer id);
        integer n;
        begin
            n=writes[id];write_reg(address,32'habcdef12,16'hffff);
            if(writes[id]!=n+1) $fatal(1,"camera write route %h",address);
            n=reads[id];read_reg(address,32'hca000000|(id<<20)|(address&32'hfff));
            if(reads[id]!=n+1) $fatal(1,"camera read route %h",address);
        end
    endtask
    initial begin #1000000;$fatal(1,"AXI128 BFM watchdog timeout");end
    initial begin
        repeat(5) @(negedge clk);rst=0;
        camera_route(32'h20000000,0);camera_route(32'h20000200,2);
        camera_route(32'h20000400,3);camera_route(32'h20000500,3);
        camera_route(32'h20000600,4);camera_route(32'h20000700,4);
        read_reg(32'h20000120,32'h12345678);
        for(c=0;c<4;c=c+1) for(j=0;j<4;j=j+1) begin
            k=(c==0)?0:c+1;before_count=reads[k];
            read_reg(32'h20000190+c*512+j*16,32'hca000000|(k<<20)|(32'h190+c*512+j*16));
            if(reads[k]!=before_count+1) $fatal(1,"CDC route camera=%0d slot=%0d",c,j);
        end
        $display("CHECK legacy: camera windows, +120 SFP diagnostic and all 16 CDC slots PASS");
        before_count=reads[1];
        read_reg(32'h20000800,0);read_reg(32'h20000810,0);read_reg(32'h20000820,0);
        read_reg(32'h20000830,32'h4d4f5431);read_reg(32'h20000840,32'h01e00280);
        read_reg(32'h20000850,32'h0c102804);
        if(reads[1]!=before_count+6) $fatal(1,"motion page not routed to PREP");
        // If high address bits were lost, this would erroneously return MOT1.
        read_reg(32'h21000830,32'hca000830);
        read_reg(32'h20000030,32'hca000030);
        $display("CHECK page: +800/+810/+820/+830/+840/+850 reachable, full address preserved PASS");
        for(c=0;c<6;c=c+1) begin
            @(posedge clk);publish=0;
            for(j=0;j<10;j=j+1) begin
                expected[j]=publication(20+c,c,j);
                records[c*320+j*32+:32]=expected[j];
            end
            write_reg(32'h20000800,32'h80000000|(c<<8),16'hffff);
            read_reg(32'h20000800,c<<8);read_reg(32'h20000820,c+1);
            // Change every camera publication continuously during reads/stalls.
            @(posedge clk);publish=1;
            for(j=0;j<10;j=j+1) begin
                write_reg(32'h20000800,j,16'hfff1);
                read_reg(32'h20000810,expected[j]);
            end
            read_reg(32'h20000820,c+1);
            $display("CHECK snapshot camera=%0d: frozen words 0..9 incl bitmap, generation=%0d PASS",c,c+1);
        end
        @(posedge clk);publish=0;
        // Upper twelve byte strobes do not select/capture anything.
        write_reg(32'h20000800,32'h80000000,16'hfff0);
        read_reg(32'h20000800,32'h509);read_reg(32'h20000820,6);
        write_reg(32'h20000800,32'h80000100,16'hfff3);
        read_reg(32'h20000800,32'h100);read_reg(32'h20000820,6);
        read_reg(32'h20000810,expected[0]);
        // Byte 3 only captures current camera/word; bytes 0/1 in data ignored.
        for(j=0;j<10;j=j+1) expected[j]=records[320+j*32+:32];
        write_reg(32'h20000800,32'h80000509,16'hfff8);
        read_reg(32'h20000800,32'h100);read_reg(32'h20000820,7);
        read_reg(32'h20000810,expected[0]);
        write_reg(32'h20000800,9,16'h0001);read_reg(32'h20000810,expected[9]);
        write_reg(32'h20000800,32'h80000600,16'hffff);
        read_reg(32'h20000810,0);read_reg(32'h20000820,7);
        write_reg(32'h20000800,32'h109,16'h0003);read_reg(32'h20000810,expected[9]);
        for(j=1;j<=5;j=j+1) write_reg(32'h20000800+j*16,32'hffffffff,16'hffff);
        read_reg(32'h20000800,32'h109);read_reg(32'h20000820,7);
        read_reg(32'h20000830,32'h4d4f5431);read_reg(32'h20000100,32'h1e);
        $display("CHECK strobes: low word only, byte merge, capture gating, invalid camera, RO isolation PASS");
        @(negedge clk);rst=1;repeat(3) @(negedge clk);rst=0;
        read_reg(32'h20000800,0);read_reg(32'h20000810,0);read_reg(32'h20000820,0);
        success=1;
        $display("PASS tb_motion_axi_bridge: writes=%0d reads=%0d R-stall-cycles=%0d live-publications=%0d; AXI128 single-beat aligned16, IDs, AW then W, frozen ten-word snapshots, reset",write_total,read_total,stall_cycles,epoch);
        $finish;
    end
endmodule

module motion_bridge_camera_stub #(parameter ID=0) (
    input clk,rst,input awvalid,output awready,input wvalid,output wready,
    output reg bvalid,input bready,output [1:0] bresp,
    input arvalid,output arready,input [31:0] araddr,
    output reg rvalid,input rready,output reg [31:0] rdata,output [1:0] rresp
);
    reg have_aw;
    assign awready=!have_aw && !bvalid;
    assign wready=have_aw && !bvalid;
    assign arready=!rvalid;
    assign bresp=0;assign rresp=0;
    always @(posedge clk) begin
        if(rst) begin have_aw<=0;bvalid<=0;rvalid<=0;rdata<=0;end
        else begin
            if(awvalid && awready) have_aw<=1;
            if(wvalid && wready) begin have_aw<=0;bvalid<=1;end
            else if(bvalid && bready) bvalid<=0;
            if(arvalid && arready) begin
                rvalid<=1;rdata<=32'hca000000|(ID<<20)|(araddr&32'hfff);
            end else if(rvalid && rready) rvalid<=0;
        end
    end
endmodule
