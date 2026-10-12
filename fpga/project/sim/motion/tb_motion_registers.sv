`timescale 1ns/1ps
module tb_motion_registers;
    reg clk=0; always #5 clk=~clk;
    reg rst=1;
    reg awvalid=0, wvalid=0, bready=0, arvalid=0, rready=0;
    reg [31:0] awaddr=0, wdata=0, araddr=0;
    reg [3:0] wstrb=0;
    wire awready,wready,bvalid,arready,rvalid;
    wire [31:0] rdata;
    wire [1:0] bresp,rresp;
    wire [4:0] mav,mwv,mbv,mbr,marv,marr,mrv,mrr,mawr,mwr;
    wire [31:0] maa[0:4], mwd[0:4], mara[0:4], mrd[0:4];
    wire [3:0] mws[0:4];
    wire [1:0] mbp[0:4], mrp[0:4];
    reg [1919:0] records=0;
    integer writes[0:4];
    integer reads[0:4];
    integer c,j,k;
    reg [31:0] expected[0:5][0:9];

    ovreg_axil_decode dec (
        .clk(clk),.rst(rst),
        .s_awvalid(awvalid),.s_awready(awready),.s_awaddr(awaddr),
        .s_wvalid(wvalid),.s_wready(wready),.s_wdata(wdata),.s_wstrb(wstrb),
        .s_bvalid(bvalid),.s_bready(bready),.s_bresp(bresp),
        .s_arvalid(arvalid),.s_arready(arready),.s_araddr(araddr),
        .s_rvalid(rvalid),.s_rready(rready),.s_rdata(rdata),.s_rresp(rresp),
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
    generate for(g=0;g<5;g=g+1) begin: cameras
        if(g!=1) begin
            motion_regs_camera_stub #(.ID(g)) cam (
                .clk(clk),.rst(rst),.awvalid(mav[g]),.awready(mawr[g]),
                .wvalid(mwv[g]),.wready(mwr[g]),.bvalid(mbv[g]),.bready(mbr[g]),.bresp(mbp[g]),
                .arvalid(marv[g]),.arready(marr[g]),.araddr(mara[g]),
                .rvalid(mrv[g]),.rready(mrr[g]),.rdata(mrd[g]),.rresp(mrp[g])
            );
        end
        always @(posedge clk) begin
            if(rst) begin writes[g]<=0; reads[g]<=0; end
            else begin
                if(mav[g] && mawr[g]) writes[g]<=writes[g]+1;
                if(marv[g] && marr[g]) reads[g]<=reads[g]+1;
            end
        end
    end endgenerate

    // Separated AW then W; mutate live address/data after each handshake.
    // Response stalls verify captured routes and stable data/response.
    task automatic write_reg(input [31:0] address,input [31:0] data,input [3:0] strobes);
        reg [1:0] resp;
        begin
            @(negedge clk); awaddr=address; awvalid=1;
            do @(posedge clk); while(!awready);
            @(negedge clk); awvalid=0; awaddr=32'h20000000;
            repeat(2) @(negedge clk);
            wdata=data; wstrb=strobes; wvalid=1;
            do @(posedge clk); while(!wready);
            @(negedge clk); wvalid=0; wdata=32'hdeadbeef; wstrb=0;
            while(!bvalid) @(negedge clk);
            resp=bresp;
            repeat(4) begin
                @(negedge clk);
                if(!bvalid || bresp!==resp) $fatal(1,"B unstable %h",address);
            end
            if(resp!==0) $fatal(1,"B error %h",address);
            bready=1; @(negedge clk); bready=0;
        end
    endtask

    task automatic read_reg(input [31:0] address,input [31:0] wanted);
        reg [31:0] held;
        reg [1:0] resp;
        begin
            @(negedge clk); araddr=address; arvalid=1;
            do @(posedge clk); while(!arready);
            @(negedge clk); arvalid=0; araddr=32'h20000000;
            while(!rvalid) @(negedge clk);
            held=rdata; resp=rresp;
            repeat(4) begin
                @(negedge clk);
                if(!rvalid || rdata!==held || rresp!==resp)
                    $fatal(1,"R unstable %h",address);
            end
            if(held!==wanted || resp!==0)
                $fatal(1,"read %h got %h expected %h resp %h",address,held,wanted,resp);
            rready=1; @(negedge clk); rready=0;
        end
    endtask

    task automatic parallel_write(input bit delay_aw);
        begin
            // Decoder supports W before AW when the pending AW address is live.
            // Hold that address/valid while PREP's AW acceptance is delayed.
            if(delay_aw) force dec.m1_awvalid=0;
            @(negedge clk); awaddr=32'h20000800; awvalid=1;
            wdata=32'h80000000; wstrb=4'hf; wvalid=1;
            fork
                begin
                    do @(posedge clk); while(!wready);
                    @(negedge clk); wvalid=0; wdata=32'hffffffff; wstrb=0;
                    if(delay_aw) begin
                        repeat(3) @(negedge clk);
                        release dec.m1_awvalid;
                    end
                end
                begin
                    do @(posedge clk); while(!awready);
                    @(negedge clk); awvalid=0; awaddr=32'h20000600;
                end
            join
            while(!bvalid) @(negedge clk);
            repeat(3) begin
                @(negedge clk);
                if(!bvalid || bresp!==0) $fatal(1,"parallel B unstable");
            end
            bready=1; @(negedge clk); bready=0;
        end
    endtask

    task automatic camera_route(input [31:0] address,input integer id);
        integer before_count;
        begin
            before_count=writes[id];
            write_reg(address,32'habcdef12,4'hf);
            if(writes[id]!=before_count+1) $fatal(1,"write route %h id %0d",address,id);
            read_reg(address,32'hca000000 | (id<<20) | (address & 32'hfff));
        end
    endtask

    initial begin
        #1000000; $fatal(1,"BFM timeout");
    end
    initial begin
        repeat(5) @(negedge clk); rst=0;
        // Main + SCCB camera windows; PREP aliases retain old behavior.
        camera_route(32'h20000000,0);
        camera_route(32'h20000200,2);
        camera_route(32'h20000400,3); camera_route(32'h20000500,3);
        camera_route(32'h20000600,4); camera_route(32'h20000700,4);
        read_reg(32'h20000100,32'h1e);
        write_reg(32'h20000104,32'h11223344,4'hf);
        write_reg(32'h20000304,32'haabbccdd,4'h5);
        read_reg(32'h20000104,32'h11bb33dd);
        read_reg(32'h20000304,32'h11bb33dd);
        // Existing aligned SFP diagnostic mux and debug slots.
        read_reg(32'h20000120,32'h12345678); read_reg(32'h20000130,32'h23456789);
        read_reg(32'h20000140,32'h3456789a); read_reg(32'h20000150,32'h456789ab);
        read_reg(32'h20000160,32'h56789abc); read_reg(32'h20000170,32'h6789abcd);
        read_reg(32'h20000180,32'h789abcde); read_reg(32'h20000184,32'h100184);
        read_reg(32'h20000188,32'h100188); read_reg(32'h2000018c,32'h10018c);
        // CDC exceptions are read-only: 190..1c0 every 0x200 camera stride.
        for(c=0;c<4;c=c+1) begin
            for(j=0;j<4;j=j+1) begin
                k=(c==0)?0:(c+1);
                read_reg(32'h20000190+c*512+j*16,
                         32'hca000000 | (k<<20) | (32'h190+c*512+j*16));
            end
        end
        // Candidate slots still follow original route, including PREP default.
        for(j=0;j<3;j=j+1) begin
            read_reg(32'h200001d0+j*16,0); read_reg(32'h200003d0+j*16,0);
            camera_route(32'h200005d0+j*16,3); camera_route(32'h200007d0+j*16,4);
        end
        read_reg(32'h20000800,0); read_reg(32'h20000810,0); read_reg(32'h20000820,0);
        read_reg(32'h20000830,32'h4d4f5431); read_reg(32'h20000840,32'h01e00280);
        read_reg(32'h20000850,32'h0c102804); read_reg(32'h20000804,0);
        for(c=0;c<6;c=c+1) begin
            // Legal record ABI with unique values in every word and camera.
            expected[c][0]=32'h12340000+c;
            expected[c][1]=c & 7;
            expected[c][2]=((16'd4800+c)<<8) | (8'd192-c);
            expected[c][3]=32'h0000b0f0;
            for(j=4;j<10;j=j+1) expected[c][j]=32'h13579bdf ^ (c<<24) ^ (j<<16);
            for(j=0;j<10;j=j+1) records[c*320+j*32+:32]=expected[c][j];
        end
        for(c=0;c<6;c=c+1) begin
            write_reg(32'h20000800,32'h80000000 | (c<<8),4'hf);
            read_reg(32'h20000800,c<<8); read_reg(32'h20000820,c+1);
            // All live words change after capture: every frozen word survives.
            @(negedge clk); records[c*320+:320]=~records[c*320+:320];
            for(j=0;j<10;j=j+1) begin
                write_reg(32'h20000800,j,4'h1);
                read_reg(32'h20000810,expected[c][j]);
            end
        end
        // Camera changes do not refresh snapshot. Upper unimplemented bits zero.
        write_reg(32'h20000800,32'hffff0002,4'h1);
        write_reg(32'h20000800,32'hffff0100,4'h2);
        read_reg(32'h20000800,32'h102); read_reg(32'h20000810,expected[5][2]);
        // Capture bit ignored unless byte 3 strobed, and zero strobes do nothing.
        write_reg(32'h20000800,32'h80000303,4'h0);
        write_reg(32'h20000800,32'h80000102,4'h3);
        read_reg(32'h20000820,6); read_reg(32'h20000810,expected[5][2]);
        // Byte-3-only command captures the already-selected camera/word.
        write_reg(32'h20000800,32'h80000509,4'h8);
        read_reg(32'h20000800,32'h102); read_reg(32'h20000820,7);
        read_reg(32'h20000810,~expected[1][2]);
        for(c=6;c<8;c=c+1) begin
            write_reg(32'h20000800,32'h80000000 | (c<<8) | 2,4'hf);
            read_reg(32'h20000810,0); read_reg(32'h20000820,7);
        end
        // Recover a valid selector: last good snapshot is still intact.
        write_reg(32'h20000800,32'h102,4'h3); read_reg(32'h20000810,~expected[1][2]);
        for(j=10;j<16;j=j+1) begin
            write_reg(32'h20000800,j,4'h1); read_reg(32'h20000810,0);
        end
        // Valid camera + invalid word captures safely; then select a valid word.
        write_reg(32'h20000800,32'h8000020f,4'hf);
        read_reg(32'h20000810,0); read_reg(32'h20000820,8);
        write_reg(32'h20000800,0,4'h1); read_reg(32'h20000810,~expected[2][0]);
        // RO/unmapped writes cannot touch selector, generation, legacy registers.
        for(j=1;j<16;j=j+1) write_reg(32'h20000800+j*16,32'hffffffff,4'hf);
        read_reg(32'h20000800,32'h200); read_reg(32'h20000820,8);
        read_reg(32'h20000100,32'h1e); read_reg(32'h20000104,32'h11bb33dd);
        read_reg(32'h20000830,32'h4d4f5431);
        @(negedge clk); rst=1; repeat(3) @(negedge clk); rst=0;
        read_reg(32'h20000800,0); read_reg(32'h20000810,0); read_reg(32'h20000820,0);
        parallel_write(0); read_reg(32'h20000820,1);
        read_reg(32'h20000810,~expected[0][0]);
        parallel_write(1); read_reg(32'h20000820,2);
        read_reg(32'h20000810,~expected[0][0]);
        $display("PASS tb_motion_registers: legacy routes, CDC/candidate slots, six-camera snapshots, strobes, invalid indices, backpressure, reset");
        $finish;
    end
endmodule

// Camera register model gives each route an identifiable read response.
module motion_regs_camera_stub #(parameter ID=0) (
    input clk,rst,input awvalid,output awready,input wvalid,output wready,
    output reg bvalid,input bready,output [1:0] bresp,
    input arvalid,output arready,input [31:0] araddr,
    output reg rvalid,input rready,output reg [31:0] rdata,output [1:0] rresp
);
    reg have_aw;
    assign awready=!have_aw && !bvalid;
    assign wready=have_aw && !bvalid;
    assign arready=!rvalid;
    assign bresp=0; assign rresp=0;
    always @(posedge clk) begin
        if(rst) begin have_aw<=0;bvalid<=0;rvalid<=0;rdata<=0; end
        else begin
            if(awvalid && awready) have_aw<=1;
            if(wvalid && wready) begin have_aw<=0;bvalid<=1; end
            else if(bvalid && bready) bvalid<=0;
            if(arvalid && arready) begin
                rvalid<=1; rdata<=32'hca000000 | (ID<<20) | (araddr & 32'hfff);
            end else if(rvalid && rready) rvalid<=0;
        end
    end
endmodule
