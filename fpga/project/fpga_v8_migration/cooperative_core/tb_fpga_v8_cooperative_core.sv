`timescale 1ns/1ps
module tb_fpga_v8_cooperative_core;
    parameter integer WIDTH=4, HEIGHT=3, OUT_HEIGHT=5, TOP_ROWS=1;
    parameter integer MODE=0, CAMERA_BURSTS=24, SEED=12345;
    parameter [31:0] BANK0=32'h08000000, BANK1=32'h08200000;
    localparam integer SRC_BYTES=WIDTH*HEIGHT*2, SRC_BUS=(SRC_BYTES+15)/16*16;
    localparam integer OUT_BYTES=WIDTH*OUT_HEIGHT*3, OUT_BUS=(OUT_BYTES+15)/16*16;
    localparam [31:0] SOURCE=32'h00100000;
    reg clk=0, rst_n=0;
    always #5 clk=~clk;
    reg input_valid=0, input_raw_valid=1;
    reg [31:0] input_src_addr=SOURCE, input_source_seq=0, input_generation=0;
    reg [2:0] input_camera=0;
    reg input_camera_bank=0;
    reg [63:0] input_lease_token=0;
    wire input_ready, input_claim, input_reject, src_release_valid;
    reg src_release_ready=0;
    wire [31:0] src_release_addr, src_release_seq, src_release_generation;
    wire [2:0] src_release_camera;
    wire src_release_camera_bank;
    wire [63:0] src_release_token;
    wire busy, bridge_busy, bridge_done, bridge_error, bridge_cmd_error;
    wire [1:0] bank0_state, bank1_state;
    wire arbiter_busy, arbiter_error;
    wire [2:0] arbiter_owner;
    wire [4:0] arbiter_error_flags;
    reg [31:0] h_awaddr=0, h_wdata=0, h_araddr=0;
    reg [3:0] h_wstrb=15;
    reg h_awvalid=0, h_wvalid=0, h_bready=0, h_arvalid=0, h_rready=0;
    wire h_awready, h_wready, h_bvalid, h_arready, h_rvalid;
    wire [1:0] h_bresp, h_rresp;
    wire [31:0] h_rdata;
    reg [23:0] camera_awid, camera_awcache, camera_awqos, camera_awregion;
    reg [191:0] camera_awaddr;
    reg [47:0] camera_awlen;
    reg [17:0] camera_awsize, camera_awprot;
    reg [11:0] camera_awburst;
    reg [5:0] camera_awlock, camera_awvalid, camera_wlast, camera_wvalid;
    reg [767:0] camera_wdata;
    reg [95:0] camera_wstrb;
    reg [5:0] camera_bready=0;
    wire [5:0] camera_awready, camera_wready, camera_bvalid;
    wire [23:0] camera_bid;
    wire [11:0] camera_bresp;
    wire [3:0] arid, arcache, arqos, arregion, awid, awcache, awqos, awregion;
    wire [31:0] araddr, awaddr;
    wire [7:0] arlen, awlen;
    wire [2:0] arsize, arprot, awsize, awprot;
    wire [1:0] arburst, awburst;
    wire arlock, arvalid, rready, awlock, awvalid, wlast, wvalid, bready;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    reg arready=0, awready=0, wready=0;
    reg [3:0] rid=0, bid=0;
    reg [127:0] rdata=0;
    reg [1:0] rresp=0, bresp=0;
    reg rlast=0, rvalid=0, bvalid=0;

    fpga_v8_cooperative_core #(
        .WIDTH(WIDTH), .HEIGHT(HEIGHT), .OUT_HEIGHT(OUT_HEIGHT), .TOP_ROWS(TOP_ROWS),
        .OUTPUT_BANK0_ADDR(BANK0), .OUTPUT_BANK1_ADDR(BANK1),
        .DDR_ADDRESS_LIMIT(32'h10000000), .AXI_ID(4'd1)
    ) dut (
        .core_clk(clk), .rst_n(rst_n), .input_valid(input_valid), .input_ready(input_ready),
        .input_raw_valid(input_raw_valid), .input_src_addr(input_src_addr),
        .input_source_seq(input_source_seq), .input_generation(input_generation),
        .input_camera(input_camera), .input_camera_bank(input_camera_bank),
        .input_lease_token(input_lease_token), .input_claim(input_claim), .input_reject(input_reject),
        .src_release_valid(src_release_valid), .src_release_ready(src_release_ready),
        .src_release_addr(src_release_addr), .src_release_seq(src_release_seq),
        .src_release_generation(src_release_generation), .src_release_camera(src_release_camera),
        .src_release_camera_bank(src_release_camera_bank), .src_release_token(src_release_token),
        .busy(busy), .bank0_state(bank0_state), .bank1_state(bank1_state),
        .bridge_busy(bridge_busy), .bridge_done(bridge_done), .bridge_error(bridge_error),
        .bridge_cmd_error(bridge_cmd_error), .arbiter_busy(arbiter_busy),
        .arbiter_owner(arbiter_owner), .arbiter_error(arbiter_error), .arbiter_error_flags(arbiter_error_flags),
        .s_axil_awaddr(h_awaddr), .s_axil_awprot(3'd0), .s_axil_awvalid(h_awvalid),
        .s_axil_awready(h_awready), .s_axil_wdata(h_wdata), .s_axil_wstrb(h_wstrb),
        .s_axil_wvalid(h_wvalid), .s_axil_wready(h_wready), .s_axil_bresp(h_bresp),
        .s_axil_bvalid(h_bvalid), .s_axil_bready(h_bready), .s_axil_araddr(h_araddr),
        .s_axil_arprot(3'd0), .s_axil_arvalid(h_arvalid), .s_axil_arready(h_arready),
        .s_axil_rdata(h_rdata), .s_axil_rresp(h_rresp), .s_axil_rvalid(h_rvalid), .s_axil_rready(h_rready),
        .camera_awid(camera_awid), .camera_awaddr(camera_awaddr), .camera_awlen(camera_awlen),
        .camera_awsize(camera_awsize), .camera_awburst(camera_awburst), .camera_awlock(camera_awlock),
        .camera_awcache(camera_awcache), .camera_awprot(camera_awprot), .camera_awqos(camera_awqos),
        .camera_awregion(camera_awregion), .camera_awvalid(camera_awvalid), .camera_awready(camera_awready),
        .camera_wdata(camera_wdata), .camera_wstrb(camera_wstrb), .camera_wlast(camera_wlast),
        .camera_wvalid(camera_wvalid), .camera_wready(camera_wready), .camera_bid(camera_bid),
        .camera_bresp(camera_bresp), .camera_bvalid(camera_bvalid), .camera_bready(camera_bready),
        .m_axi_read_arid(arid), .m_axi_read_araddr(araddr), .m_axi_read_arlen(arlen),
        .m_axi_read_arsize(arsize), .m_axi_read_arburst(arburst), .m_axi_read_arlock(arlock),
        .m_axi_read_arcache(arcache), .m_axi_read_arprot(arprot), .m_axi_read_arqos(arqos),
        .m_axi_read_arregion(arregion), .m_axi_read_arvalid(arvalid), .m_axi_read_arready(arready),
        .m_axi_read_rid(rid), .m_axi_read_rdata(rdata), .m_axi_read_rresp(rresp),
        .m_axi_read_rlast(rlast), .m_axi_read_rvalid(rvalid), .m_axi_read_rready(rready),
        .m_axi_write_awid(awid), .m_axi_write_awaddr(awaddr), .m_axi_write_awlen(awlen),
        .m_axi_write_awsize(awsize), .m_axi_write_awburst(awburst), .m_axi_write_awlock(awlock),
        .m_axi_write_awcache(awcache), .m_axi_write_awprot(awprot), .m_axi_write_awqos(awqos),
        .m_axi_write_awregion(awregion), .m_axi_write_awvalid(awvalid), .m_axi_write_awready(awready),
        .m_axi_write_wdata(wdata), .m_axi_write_wstrb(wstrb), .m_axi_write_wlast(wlast),
        .m_axi_write_wvalid(wvalid), .m_axi_write_wready(wready), .m_axi_write_bid(bid),
        .m_axi_write_bresp(bresp), .m_axi_write_bvalid(bvalid), .m_axi_write_bready(bready)
    );

    reg [7:0] source_mem[0:SRC_BUS-1], golden_mem[0:OUT_BYTES-1];
    reg [7:0] output0[0:OUT_BUS+15], output1[0:OUT_BUS+15];
    reg [7:0] camera_mem[0:6*CAMERA_BURSTS*256-1];
    integer cam_state[0:5], cam_tx[0:5], cam_beat[0:5];
    integer camera_words[0:5], camera_responses[0:5];
    reg [5:0] cam_offer=0;
    reg cameras_enable=0;
    reg [31:0] rng=SEED;
    integer cycles=0, total_cycles=0, releases=0, claims=0, publishes=0;
    integer read_count=0, bridge_words=0, bridge_bs=0, copied_bytes=0;
    integer trace_fd, i, j;
    reg force_ar=0, force_aw=0, force_w=0, hold_final_b=0;
    integer inject_r=0, inject_b=0;
    reg leased=0, retired=0;
    reg [31:0] leased_addr, leased_seq, leased_gen;
    reg [2:0] leased_camera;
    reg leased_bank;
    reg [63:0] leased_token;
    reg expected_failure=0;

    function integer burst_beats(input integer tx);
        case (tx%4)
            0: burst_beats=16;
            1: burst_beats=3;
            2: burst_beats=5;
            default: burst_beats=1;
        endcase
    endfunction
    function [7:0] cam_byte(input integer owner, tx, beat, lane);
        cam_byte=(owner*37+tx*19+beat*11+lane*7)&255;
    endfunction
    function [127:0] cam_word(input integer owner, tx, beat);
        integer lane;
        for (lane=0; lane<16; lane=lane+1)
            cam_word[lane*8+:8]=cam_byte(owner,tx,beat,lane);
    endfunction
    function [31:0] cam_addr(input integer owner, tx);
        cam_addr=32'h01000000+owner*32'h00100000+tx*256;
    endfunction
    function [31:0] generation(input integer seq);
        generation=32'h12340000+seq;
    endfunction
    function [63:0] token(input integer seq);
        token=64'hcafebabe00000000+seq;
    endfunction
    task fail(input string message);
        $display("CORE_FAIL cycle=%0d %s", total_cycles,message);
        $fatal(1,"%s",message);
    endtask

    integer ci;
    always @* begin
        camera_awid=0; camera_awaddr=0; camera_awlen=0; camera_awsize=0;
        camera_awburst=0; camera_awlock=0; camera_awcache=0; camera_awprot=0;
        camera_awqos=0; camera_awregion=0; camera_awvalid=0;
        camera_wdata=0; camera_wstrb=0; camera_wlast=0; camera_wvalid=0;
        for(ci=0;ci<6;ci=ci+1) begin
            camera_awid[ci*4+:4]=ci+8;
            camera_awaddr[ci*32+:32]=cam_addr(ci,cam_tx[ci]);
            camera_awlen[ci*8+:8]=burst_beats(cam_tx[ci])-1;
            camera_awsize[ci*3+:3]=4;
            camera_awburst[ci*2+:2]=1;
            camera_awcache[ci*4+:4]=ci;
            camera_awprot[ci*3+:3]=ci;
            camera_awqos[ci*4+:4]=ci+2;
            camera_awregion[ci*4+:4]=ci+3;
            camera_awvalid[ci]=rst_n && cameras_enable && cam_state[ci]==0;
            camera_wdata[ci*128+:128]=cam_word(ci,cam_tx[ci],cam_beat[ci]);
            camera_wstrb[ci*16+:16]=16'hffff;
            camera_wlast[ci]=cam_beat[ci]==burst_beats(cam_tx[ci])-1;
            camera_wvalid[ci]=rst_n && cameras_enable && cam_state[ci]==1 && cam_offer[ci];
        end
    end
    integer driver_i;
    always @(posedge clk) begin
        total_cycles<=total_cycles+1;
        if(!rst_n) begin
            cycles<=0; rng<=SEED; camera_bready<=0; cam_offer<=0;
            for(driver_i=0;driver_i<6;driver_i=driver_i+1) begin
                cam_state[driver_i]<=0; cam_tx[driver_i]<=0; cam_beat[driver_i]<=0;
                camera_words[driver_i]<=0; camera_responses[driver_i]<=0;
            end
        end else begin
            cycles<=cycles+1;
            rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            camera_bready<=rng[5:0];
            for(driver_i=0;driver_i<6;driver_i=driver_i+1) begin
                if(camera_awvalid[driver_i] && camera_awready[driver_i]) begin
                    cam_state[driver_i]<=1; cam_offer[driver_i]<=1;
                end
                if(cam_state[driver_i]==1 && (!cam_offer[driver_i] || camera_wready[driver_i]))
                    cam_offer[driver_i]<=rng[driver_i+8];
                if(camera_wvalid[driver_i] && camera_wready[driver_i]) begin
                    camera_words[driver_i]<=camera_words[driver_i]+1;
                    if(camera_wlast[driver_i]) cam_state[driver_i]<=2;
                    else cam_beat[driver_i]<=cam_beat[driver_i]+1;
                end
                if(camera_bvalid[driver_i] && camera_bready[driver_i]) begin
                    if(camera_bid[driver_i*4+:4] !== driver_i+8 ||
                       camera_bresp[driver_i*2+:2] !== 2'd0) fail("camera B ID/response routing");
                    camera_responses[driver_i]<=camera_responses[driver_i]+1;
                    cam_tx[driver_i]<=cam_tx[driver_i]+1; cam_beat[driver_i]<=0;
                    cam_state[driver_i]<=(cam_tx[driver_i]+1==CAMERA_BURSTS)?3:0;
                end
            end
        end
    end

    reg read_pending=0;
    reg [31:0] read_address;
    integer rdelay=0;
    reg write_active=0, response_pending=0;
    integer write_owner=-1, write_tx=0, write_beat=0, write_beats=0;
    reg [31:0] write_address;
    reg [3:0] write_id;
    integer bdelay=0;
    reg final_response=0;
    integer mi, address_index, memory_index;
    // A 128-bit DDR slave with independent randomized address/data/response stalls.
    always @(posedge clk) begin
        if(!rst_n) begin
            arready<=0; awready<=0; wready<=0; rvalid<=0; bvalid<=0;
            rid<=0; rdata<=0; rresp<=0; rlast<=0; bid<=0; bresp<=0;
            read_pending<=0; write_active<=0; response_pending<=0;
            final_response<=0; rdelay<=0; bdelay<=0;
            read_count<=0; bridge_words<=0; bridge_bs<=0;
        end else begin
            arready<=!force_ar && !read_pending && !rvalid && (rng[6] || rng[7]);
            awready<=!force_aw && !write_active && !response_pending && !bvalid && rng[12];
            wready<=!force_w && write_active && (rng[13] || rng[14]);
            if(arvalid && arready) begin
                if(!leased) fail("DDR reads outside input lease");
                if({arid,arlen,arsize,arburst,arlock,arcache,arprot,arqos,arregion} !==
                   {4'd1,8'd0,3'd4,2'd1,1'b0,4'd3,3'd0,4'd0,4'd0}) fail("full AR payload");
                if(araddr !== SOURCE+read_count*16 || araddr+16>SOURCE+SRC_BUS) fail("AR range/order");
                read_count<=read_count+1; read_pending<=1; read_address<=araddr;
                rdelay<=1+(rng[18:16]%6); arready<=0;
            end
            if(read_pending && !rvalid) begin
                if(rdelay>0) rdelay<=rdelay-1;
                else begin
                    for(mi=0;mi<16;mi=mi+1) rdata[mi*8+:8]<=source_mem[read_address-SOURCE+mi];
                    rid<=1; rlast<=1; rresp<=(inject_r!=0)?2'b10:2'b00;
                    if(inject_r!=0) inject_r<=0;
                    rvalid<=1;
                end
            end
            if(rvalid && rready) begin rvalid<=0; read_pending<=0; end
            if(awvalid && awready) begin
                if(write_active || response_pending || bvalid) fail("overlapping write ownership");
                write_active<=1; write_address<=awaddr; write_id<=awid;
                write_beat<=0; write_beats<=awlen+1; awready<=0;
                if(awaddr>=32'h01000000 && awaddr<32'h01600000) begin
                    address_index=(awaddr-32'h01000000)/32'h00100000;
                    memory_index=(awaddr-cam_addr(address_index,0))/256;
                    write_owner<=address_index; write_tx<=memory_index;
                    if(memory_index>=CAMERA_BURSTS) fail("camera AW bounds");
                    if(awaddr !== cam_addr(address_index,memory_index) || awid !== address_index+8 ||
                       awlen !== burst_beats(memory_index)-1 || awsize !== 3'd4 || awburst !== 2'd1 ||
                       awlock !== 1'b0 || awcache !== address_index || awprot !== address_index ||
                       awqos !== address_index+2 || awregion !== address_index+3) fail("camera full AW routing");
                end else begin
                    write_owner<=6;
                    if(awaddr<BANK0 || (awaddr>=BANK0+OUT_BUS && awaddr<BANK1) || awaddr>=BANK1+OUT_BUS)
                        fail("output AW range");
                    if({awid,awlen,awsize,awburst,awlock,awcache,awprot,awqos,awregion} !==
                       {4'd1,8'd0,3'd4,2'd1,1'b0,4'd3,3'd0,4'd0,4'd0}) fail("bridge full AW payload");
                    if(dut.bridge.write_keep === 16'd0 || $isunknown({dut.bridge.write_keep,dut.bridge.write_data}))
                        fail("bridge requested AW before packed data existed");
                    if(awaddr !== (dut.bridge.active_dst_addr+bridge_words*16)) fail("output address order");
                end
                $fwrite(trace_fd,"AW %0d %08x %0d %0d\n",total_cycles,awaddr,awid,awlen+1);
            end
            if(wvalid && wready) begin
                if(!write_active) fail("W without AW");
                if(wlast !== (write_beat+1==write_beats)) fail("WLAST/length");
                if(write_owner<6) begin
                    if(wdata !== cam_word(write_owner,write_tx,write_beat) || wstrb !== 16'hffff)
                        fail("camera complete W word/strb routing");
                    for(mi=0;mi<16;mi=mi+1)
                        camera_mem[(write_owner*CAMERA_BURSTS+write_tx)*256+write_beat*16+mi]<=wdata[mi*8+:8];
                end else begin
                    address_index=write_address-dut.bridge.active_dst_addr;
                    if(wstrb !== ((OUT_BYTES-address_index>=16)?16'hffff:((1<<(OUT_BYTES-address_index))-1)))
                        fail("partial output WSTRB");
                    for(mi=0;mi<16;mi=mi+1) begin
                        if(wstrb[mi]) begin
                            if(wdata[mi*8+:8] !== golden_mem[address_index+mi]) fail("complete output byte compare");
                            if(dut.bridge.active_dst_addr==BANK0) output0[address_index+mi]<=wdata[mi*8+:8];
                            else output1[address_index+mi]<=wdata[mi*8+:8];
                        end
                    end
                    bridge_words<=bridge_words+1;
                end
                $fwrite(trace_fd,"W %0d %0d %0d %032x %04x\n",write_owner,write_tx,write_beat,wdata,wstrb);
                write_beat<=write_beat+1;
                if(write_beat+1==write_beats) begin
                    write_active<=0; response_pending<=1; wready<=0;
                    bdelay<=2+(rng[22:19]%9);
                    final_response<=write_owner==6 && write_address==dut.bridge.active_dst_addr+OUT_BUS-16;
                end
            end
            if(response_pending && !bvalid) begin
                if(bdelay>0) bdelay<=bdelay-1;
                else if(!(hold_final_b && final_response)) begin
                    bid<=write_id; bresp<=(inject_b!=0 && write_owner==6 && final_response)?2'b10:2'b00;
                    if(inject_b!=0 && write_owner==6 && final_response) inject_b<=0;
                    bvalid<=1;
                end
            end
            if(bvalid && bready) begin
                $fwrite(trace_fd,"B %0d %0d %0d\n",write_owner,bid,bresp);
                if(write_owner==6) bridge_bs<=bridge_bs+1;
                bvalid<=0; response_pending<=0; final_response<=0;
            end
        end
    end

    integer rr_start=0, rr_expected, rr_offset, selections=0;
    reg [6:0] request_mask;
    reg [1:0] prev_bank0=0, prev_bank1=0;
    reg stalled_aw=0, stalled_w=0, stalled_ar=0, stalled_r=0, stalled_b=0;
    reg [64:0] aw_snapshot, ar_snapshot;
    reg [144:0] w_snapshot;
    reg [134:0] r_snapshot;
    reg [5:0] b_snapshot;
    reg stalled_release=0;
    reg [163:0] release_snapshot;
    reg bridge_staged=0;
    // Ownership/lease scoreboard observes handshakes independently of the DUT FSM.
    always @(posedge clk) begin
        if(!rst_n) begin
            leased=0; retired=0; rr_start=0; selections=0;
            prev_bank0=0; prev_bank1=0;
            bridge_staged=0;
            stalled_aw=0; stalled_w=0; stalled_ar=0; stalled_r=0; stalled_b=0; stalled_release=0;
        end else begin
            if($isunknown({input_ready,input_claim,input_reject,src_release_valid,busy,bank0_state,bank1_state,
                bridge_busy,bridge_done,bridge_error,bridge_cmd_error,arbiter_busy,arbiter_owner,
                arbiter_error,arbiter_error_flags,camera_awready,camera_wready,camera_bvalid,
                h_awready,h_wready,h_bvalid,h_arready,h_rvalid,arvalid,rready,awvalid,wvalid,bready}))
                fail("unknown control output");
            if(dut.bridge.packed_valid && dut.bridge.packed_ready) bridge_staged=1;
            if(dut.bridge_awvalid && !bridge_staged) fail("m6 AW before packed-word capture");
            if(dut.bridge_bvalid && dut.bridge_bready) bridge_staged=0;
            if(stalled_aw && (!awvalid || {awid,awaddr,awlen,awsize,awburst,awlock,awcache,awprot,awqos,awregion} !== aw_snapshot)) fail("AW unstable");
            if(stalled_w && (!wvalid || {wdata,wstrb,wlast} !== w_snapshot)) fail("W unstable");
            if(stalled_ar && (!arvalid || {arid,araddr,arlen,arsize,arburst,arlock,arcache,arprot,arqos,arregion} !== ar_snapshot)) fail("AR unstable");
            if(stalled_r && (!rvalid || {rid,rdata,rresp,rlast} !== r_snapshot)) fail("R unstable");
            if(stalled_b && (!bvalid || {bid,bresp} !== b_snapshot)) fail("B unstable");
            if(stalled_release && (!src_release_valid || {src_release_addr,src_release_seq,src_release_generation,
                src_release_camera,src_release_camera_bank,src_release_token} !== release_snapshot)) fail("release unstable");
            stalled_aw=awvalid&&!awready; aw_snapshot={awid,awaddr,awlen,awsize,awburst,awlock,awcache,awprot,awqos,awregion};
            stalled_ar=arvalid&&!arready; ar_snapshot={arid,araddr,arlen,arsize,arburst,arlock,arcache,arprot,arqos,arregion};
            stalled_w=wvalid&&!wready; w_snapshot={wdata,wstrb,wlast};
            stalled_r=rvalid&&!rready; r_snapshot={rid,rdata,rresp,rlast};
            stalled_b=bvalid&&!bready; b_snapshot={bid,bresp};
            stalled_release=src_release_valid&&!src_release_ready;
            release_snapshot={src_release_addr,src_release_seq,src_release_generation,src_release_camera,src_release_camera_bank,src_release_token};
            if(dut.write_arbiter.state==0) begin
                request_mask={dut.bridge_awvalid,camera_awvalid}; rr_expected=-1;
                for(rr_offset=0;rr_offset<7;rr_offset=rr_offset+1)
                    if(rr_expected<0 && request_mask[(rr_start+rr_offset)%7]) rr_expected=(rr_start+rr_offset)%7;
                if(rr_expected>=0) begin
                    if(dut.write_arbiter.pick !== rr_expected) fail("RR choice differs from independent scoreboard");
                    selections=selections+1;
                    $fwrite(trace_fd,"SELECT %0d %0d %02x %0d\n",total_cycles,rr_start,request_mask,rr_expected);
                end
            end
            if(bvalid && bready) rr_start=(write_owner+1)%7;
            if(input_claim) begin
                if(leased) fail("source reused before release");
                leased=1; retired=0; claims=claims+1;
                leased_addr=input_src_addr; leased_seq=input_source_seq; leased_gen=input_generation;
                leased_camera=input_camera; leased_bank=input_camera_bank; leased_token=input_lease_token;
            end
            if(bridge_done || (bridge_cmd_error && !bridge_busy)) retired=1;
            if(src_release_valid) begin
                if(!leased || !retired || bridge_busy || read_pending || rvalid ||
                   (arbiter_busy && arbiter_owner==6)) fail("source release before transaction retirement");
                if({src_release_addr,src_release_seq,src_release_generation,src_release_camera,src_release_camera_bank,src_release_token} !==
                   {leased_addr,leased_seq,leased_gen,leased_camera,leased_bank,leased_token}) fail("lease metadata changed");
                if(src_release_ready) begin leased=0; releases=releases+1; end
            end
            if((bank0_state==2 && prev_bank0!=2) || (bank1_state==2 && prev_bank1!=2)) begin
                if(expected_failure || !retired || bridge_bs!=OUT_BUS/16) fail("premature/failed output publication");
                publishes=publishes+1;
            end
            prev_bank0=bank0_state; prev_bank1=bank1_state;
            if(arbiter_error && !(MODE==1 && arbiter_error_flags==5'b00100)) fail("unexpected arbiter diagnostics");
        end
    end

    task tick(input integer n);
        repeat(n) @(negedge clk);
    endtask
    task common_reset;
        begin
            @(negedge clk); rst_n=0; input_valid=0; src_release_ready=0;
            h_awvalid=0; h_wvalid=0; h_bready=0; h_arvalid=0; h_rready=0;
            cameras_enable=0; force_ar=0; force_aw=0; force_w=0; hold_final_b=0;
            inject_r=0; inject_b=0; expected_failure=0;
            for(i=0;i<OUT_BUS+16;i=i+1) begin output0[i]=8'ha5; output1[i]=8'ha5; end
            for(i=0;i<6*CAMERA_BURSTS*256;i=i+1) camera_mem[i]=8'ha5;
            tick(5); rst_n=1; tick(3);
            if(bank0_state!==0 || bank1_state!==0 || busy || bridge_busy || arbiter_busy || src_release_valid)
                fail("common reset failed to clear outstanding state");
            $fwrite(trace_fd,"RESET\n");
        end
    endtask
    task offer(input integer seq, input bit failed);
        string name;
        begin
            if(leased) fail("source memory overwrite while leased");
            name=$sformatf("source_%0d.hex",seq); $readmemh(name,source_mem);
            name=$sformatf("golden_%0d.hex",seq); $readmemh(name,golden_mem);
            read_count=0; bridge_words=0; bridge_bs=0; expected_failure=failed;
            @(negedge clk); input_source_seq=seq; input_generation=generation(seq);
            input_camera=seq%6; input_camera_bank=seq%2; input_lease_token=token(seq);
            input_src_addr=SOURCE; input_raw_valid=1; input_valid=1;
            do @(posedge clk); while(!input_ready);
            @(negedge clk); input_valid=0;
            // Poison live descriptor after acceptance: all later metadata is captured.
            input_src_addr=32'hdeadbeef; input_source_seq=32'hbad00000;
            input_generation=0; input_camera=7; input_camera_bank=0; input_lease_token=0;
        end
    endtask
    task await_release(input bit failed);
        integer before_releases;
        begin
            wait(src_release_valid); @(negedge clk);
            if(failed && (bank0_state!==0 || bank1_state!==0)) fail("failed output not FREE");
            if(!failed && bank0_state!=2 && bank1_state!=2) fail("success output not READY");
            tick(7);
            if(input_ready || !leased) fail("release backpressure did not retain lease");
            before_releases=releases; src_release_ready=1; tick(1); src_release_ready=0; tick(2);
            if(leased || releases!=before_releases+1) fail("lease release handshake");
        end
    endtask
    task host_write(input [31:0] address, value, input [1:0] response, input bit w_first);
        reg [1:0] held;
        begin
            @(negedge clk); h_awaddr=address; h_wdata=value; h_wstrb=15; h_bready=0;
            if(w_first) begin
                h_wvalid=1; do @(posedge clk); while(!h_wready);
                @(negedge clk); h_wvalid=0; tick(3); h_awvalid=1;
                do @(posedge clk); while(!h_awready); @(negedge clk); h_awvalid=0;
            end else begin
                h_awvalid=1; do @(posedge clk); while(!h_awready);
                @(negedge clk); h_awvalid=0; tick(2); h_wvalid=1;
                do @(posedge clk); while(!h_wready); @(negedge clk); h_wvalid=0;
            end
            wait(h_bvalid); @(negedge clk); held=h_bresp;
            repeat(5) begin
                tick(1);
                if(!h_bvalid || h_bresp!==held || h_awready || h_wready) fail("AXIL blocked B behavior");
            end
            if(held!==response) fail($sformatf("AXIL write %08x response %0d expected %0d",address,held,response));
            h_bready=1; tick(1); h_bready=0; tick(1);
        end
    endtask
    task host_read(input [31:0] address, output [31:0] value);
        reg [31:0] held;
        begin
            @(negedge clk); h_araddr=address; h_arvalid=1; h_rready=0;
            do @(posedge clk); while(!h_arready); @(negedge clk); h_arvalid=0;
            wait(h_rvalid); @(negedge clk); held=h_rdata;
            repeat(4) begin
                tick(1); if(!h_rvalid || h_rdata!==held || h_rresp!==0 || h_arready) fail("AXIL R stall stability");
            end
            value=held; h_rready=1; tick(1); h_rready=0; tick(1);
        end
    endtask
    task host_pending_channels;
        reg [31:0] value;
        begin
            // Submit a second complete write while the first B is blocked.
            @(negedge clk); h_awaddr='h40; h_wdata=0; h_awvalid=1; h_wvalid=1; h_bready=0;
            do @(posedge clk); while(!(h_awready && h_wready));
            @(negedge clk); h_awvalid=0; h_wvalid=0;
            wait(h_bvalid); @(negedge clk);
            h_awaddr='h44; h_wdata=32'h11223344; h_awvalid=1; h_wvalid=1;
            repeat(7) begin
                tick(1); if(h_awready || h_wready || !h_bvalid || h_bresp!==0) fail("queued host write while B blocked");
            end
            h_bready=1; tick(1); h_bready=0;
            do @(posedge clk); while(!(h_awready && h_wready));
            @(negedge clk); h_awvalid=0; h_wvalid=0;
            wait(h_bvalid); @(negedge clk);
            if(h_bresp!==0) fail("queued host write response");
            h_bready=1; tick(1); h_bready=0; tick(2);
            host_read('h44,value); if(value!==32'h11223344) fail("queued host write lost/duplicated");
            // Hold the next AR while R is stalled, then accept both at one edge.
            @(negedge clk); h_araddr=0; h_arvalid=1; h_rready=0;
            do @(posedge clk); while(!h_arready);
            @(negedge clk); h_arvalid=0;
            wait(h_rvalid); @(negedge clk); h_araddr=8; h_arvalid=1;
            repeat(6) begin
                tick(1); if(h_arready || !h_rvalid || h_rdata!==32'h434f4f50 || h_rresp!==0)
                    fail("queued host AR while R stalled");
            end
            h_rready=1;
            @(posedge clk); if(!h_arready || !h_rvalid || h_rdata!==32'h434f4f50) fail("AXIL simultaneous R/AR");
            @(negedge clk); h_arvalid=0; h_rready=0;
            repeat(4) begin
                tick(1); if(!h_rvalid || h_rdata!==32'h00010000 || h_rresp!==0) fail("replacement AXIL R response");
            end
            h_rready=1; tick(1); h_rready=0; tick(2);
        end
    endtask
    task check_desc(input integer bank, seq);
        reg [31:0] value;
        begin
            host_read('h10,value); if(value!==bank) fail("claim bank descriptor");
            host_read('h14,value); if(value!==seq) fail("claim sequence descriptor");
            host_read('h18,value); if(value!==generation(seq)) fail("claim generation descriptor");
            host_read('h1c,value); if(value!==OUT_BYTES) fail("claim byte length");
            host_read('h20,value); if(value!==(bank?BANK1:BANK0)) fail("claim output address");
            host_read('h24,value); if(value!==seq%6) fail("claim camera");
            host_read('h28,value); if(value!==seq%2) fail("claim camera bank");
            host_read('h2c,value); if(value!==SOURCE) fail("claim source");
            host_read('h34,value); if(value!==seq) fail("claim token low");
            host_read('h38,value); if(value!==32'hcafebabe) fail("claim token high");
        end
    endtask
    task host_copy(input integer bank, seq);
        integer fd, k;
        string name;
        begin
            name=$sformatf("output_%0d.bin",seq); fd=$fopen(name,"wb");
            if(!fd) fail("output dump open");
            // Host memory copy is a behavioral reader of the DDR byte arrays.
            // It intentionally occurs before ACK and includes every output byte.
            for(k=0;k<OUT_BYTES;k=k+1) begin
                if($isunknown(bank?output1[k]:output0[k])) fail("unknown output memory byte");
                $fwrite(fd,"%c",bank?output1[k]:output0[k]);
            end
            $fclose(fd); copied_bytes=copied_bytes+OUT_BYTES;
            for(k=OUT_BYTES;k<OUT_BUS+16;k=k+1)
                if((bank?output1[k]:output0[k])!==8'ha5) fail("unstrobed/guard output byte changed");
            tick(5);
        end
    endtask
    task ack(input integer bank, seq, gen, input [1:0] response);
        begin
            host_write('h40,bank,0,0); host_write('h44,seq,0,1);
            host_write('h48,gen,0,0); host_write('h4c,1,response,1);
        end
    endtask
    task copy_ack(input integer bank, seq);
        begin
            host_write('h30,bank,0,1); check_desc(bank,seq); host_copy(bank,seq);
            ack(bank,seq,generation(seq),0);
            if((bank?bank1_state:bank0_state)!==0) fail("ACK did not free bank");
        end
    endtask
    task cameras_finish;
        integer k, tx, beat, lane, expected_words, fd;
        begin
            wait(cam_state[0]==3 && cam_state[1]==3 && cam_state[2]==3 && cam_state[3]==3 && cam_state[4]==3 && cam_state[5]==3);
            tick(3); expected_words=0;
            for(tx=0;tx<CAMERA_BURSTS;tx=tx+1) expected_words=expected_words+burst_beats(tx);
            fd=$fopen("camera_output.bin","wb");
            for(k=0;k<6;k=k+1) begin
                if(camera_words[k]!=expected_words || camera_responses[k]!=CAMERA_BURSTS) fail("camera word/B counts");
                for(tx=0;tx<CAMERA_BURSTS;tx=tx+1)
                    for(beat=0;beat<16;beat=beat+1)
                        for(lane=0;lane<16;lane=lane+1) begin
                            if(camera_mem[(k*CAMERA_BURSTS+tx)*256+beat*16+lane] !==
                               ((beat<burst_beats(tx))?cam_byte(k,tx,beat,lane):8'ha5)) fail("camera full memory/guard compare");
                            $fwrite(fd,"%c",camera_mem[(k*CAMERA_BURSTS+tx)*256+beat*16+lane]);
                        end
            end
            $fclose(fd);
        end
    endtask

    reg [31:0] value;
    integer phase, before_pub;
    initial begin
        trace_fd=$fopen("trace.txt","w");
        common_reset(); cameras_enable=1;
        host_read(0,value); if(value!==32'h434f4f50) fail("host endpoint device ID");
        if(MODE==0) begin
            host_pending_channels();
            // Invalid RAW certification rejects without acquiring a source lease.
            @(negedge clk); input_raw_valid=0; input_valid=1;
            @(posedge clk); if(!input_reject || input_claim) fail("non-RAW descriptor rejection");
            @(negedge clk); input_valid=0; input_raw_valid=1;
            hold_final_b=1; offer(1,0); wait(final_response);
            tick(35);
            if(bank0_state!==1 || src_release_valid || !leased || !bridge_busy || bridge_done)
                fail("last B hold published/released frame");
            host_write('h30,0,2,0);
            hold_final_b=0; await_release(0);
            offer(2,0); await_release(0);
            if(bank0_state!==2 || bank1_state!==2) fail("two READY banks");
            @(negedge clk); input_valid=1;
            repeat(12) begin tick(1); if(input_ready || input_claim) fail("both outputs owned input backpressure"); end
            input_valid=0;
            host_write('h30,0,0,1); check_desc(0,1);
            // A second claim is rejected while an existing descriptor remains bound.
            host_write('h30,1,2,0); check_desc(0,1);
            ack(0,99,generation(1),2);
            if(bank0_state!==3 || bank1_state!==2 || input_ready) fail("stale sequence ACK freed bank");
            ack(0,1,generation(1)+1,2);
            if(bank0_state!==3) fail("stale generation ACK freed bank");
            check_desc(0,1); host_copy(0,1); ack(0,1,generation(1),0);
            // Fill a newly free output while host reads the other claimed bank.
            host_write('h30,1,0,0); check_desc(1,2);
            offer(3,0); await_release(0); check_desc(1,2);
            host_copy(1,2); ack(1,2,generation(2),0); copy_ack(0,3);
            host_read('h50,value); if(value!==2) fail("stale ACK counter");
            host_read('h60,value); if(value!==3) fail("completed counter");
        end else if(MODE==1) begin
            inject_r=1; offer(1,1); await_release(1);
            host_write('h30,0,2,0);
            if(read_count!=SRC_BUS/16 || bridge_bs!=OUT_BUS/16) fail("RRESP fault did not drain frame");
            inject_b=1; hold_final_b=1; offer(2,1); wait(final_response); tick(20);
            if(bank0_state!==1 || src_release_valid || !leased) fail("BRESP fault released before final retirement");
            hold_final_b=0; await_release(1);
            if(read_count!=SRC_BUS/16 || bridge_bs!=OUT_BUS/16) fail("BRESP fault did not drain frame");
            offer(3,0); await_release(0); copy_ack(0,3);
            host_read('h5c,value); if(value!==2) fail("bridge failure counter");
            host_read('h60,value); if(value!==1) fail("failed frames published");
        end else if(MODE==2) begin
            for(phase=0;phase<4;phase=phase+1) begin
                if(phase==0) force_ar=1;
                if(phase==1) force_aw=1;
                if(phase==2) force_w=1;
                if(phase==3) hold_final_b=1;
                offer(phase+1,0);
                case(phase)
                    0: wait(arvalid && !arready);
                    1: wait(awvalid && !awready);
                    2: wait(wvalid && !wready);
                    3: wait(final_response);
                endcase
                tick(12); if(!leased || src_release_valid) fail("reset phase unexpectedly retired");
                common_reset(); tick(15);
                if(bridge_done || src_release_valid || bank0_state!=0 || bank1_state!=0) fail("ghost completion after reset");
                cameras_enable=1;
            end
            offer(5,0); await_release(0); copy_ack(0,5);
        end else if(MODE==3) begin
            // Invalid configured output address is rejected by the bridge.
            // The control layer must retire the no-launch rejection and release.
            offer(1,1); await_release(1);
            if(read_count!=0 || bridge_words!=0 || bridge_bs!=0) fail("invalid output launched AXI");
            offer(2,1); await_release(1);
            if(read_count!=0 || bridge_words!=0 || bridge_bs!=0) fail("repeated invalid output launched AXI");
            host_read('h5c,value); if(value!==2) fail("invalid output failures");
        end else if(MODE==4) begin
            hold_final_b=1; offer(1,0); wait(final_response); tick(40);
            if(bank0_state!==1 || src_release_valid || !leased) fail("full frame published before final B");
            hold_final_b=0; await_release(0); copy_ack(0,1);
        end else fail("unknown MODE");
        cameras_finish(); tick(10);
        if(bank0_state!==0 || bank1_state!==0 || busy || bridge_busy || src_release_valid || leased) fail("final ownership not idle/free");
        if(MODE!=2 && claims!=releases) fail("source lease balance");
        if(MODE==2 && claims!=releases+4) fail("common reset lease reconciliation");
        $fclose(trace_fd);
        $display("CORE_PASS mode=%0d cycles=%0d claims=%0d releases=%0d publishes=%0d copied_bytes=%0d camera_bursts=%0d",MODE,total_cycles,claims,releases,publishes,copied_bytes,CAMERA_BURSTS*6);
        $finish;
    end
    initial begin
        repeat(12000000) @(posedge clk);
        fail("simulation watchdog");
    end
endmodule
