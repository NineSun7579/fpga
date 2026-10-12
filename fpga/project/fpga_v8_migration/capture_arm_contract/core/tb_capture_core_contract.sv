`timescale 1ns/1ps
module tb_capture_core_contract;
    parameter WIDTH=16, HEIGHT=16, OUT_HEIGHT=24, TOP_ROWS=4, MODE=0, CAMERA_BURSTS=8;
    localparam RAW_BYTES=WIDTH*HEIGHT*2, WORDS=RAW_BYTES/16;
    localparam OUT_BYTES=WIDTH*OUT_HEIGHT*3, OUT_WORDS=(OUT_BYTES+15)/16;
    localparam B0=32'h01800000, B1=32'h01a00000;
    localparam O0=32'h08000000, O1=32'h08200000;
    reg clk=0, rst_n=0;
    always #5 clk=~clk;
    GTP_GRS GRS_INST(.GRS_N(1'b1));
    reg sv=0, pv=0;
    reg [15:0] pixel=0;
    wire admit, capture_bank, publish, retired, idle, flush, good, overflow;
    wire [31:0] pubseq, ctrl_state, last_cnt;
    wire [15:0] credits;
    wire [127:0] camera_data;
    wire camera_dvalid, camera_dready, cmd_valid, cmd_ready, dma_done, dma_abort, abort_req;
    wire [31:0] cmd_addr, cmd_len;
    wire [1:0] legacy_req;
    reg [1:0] legacy_ack=0;
    wire cfgv;
    wire [31:0] cfggen;
    wire cfgr, cfga, cfgx, epoch, armed, cfgok, lease_block, lease_fault;
    wire [1:0] rawstate0,rawstate1;
    wire [31:0] pub_count,fail_count,reject_count;
    wire iv,ir,rawvalid,ibank;
    wire [31:0] ia,il,iseq,igen;
    wire [2:0] icam;
    wire [63:0] itoken;
    wire input_claim, input_reject;
    wire relv, relr, relbank, rela, relx;
    wire [31:0] reladdr,relseq,relgen;
    wire [2:0] relcam;
    wire [63:0] reltoken;
    wire hv,hbank;
    reg hr=0,hrv=0;
    wire hrr,hra,hrx;
    wire [31:0] ha,hl,hseq,hgen;
    wire [2:0] hcam;
    wire [63:0] htoken;
    reg [2:0] hrcam=4;
    reg hrbank=0;
    reg [31:0] hrseq=0,hrgen=0;
    reg [63:0] hrtoken=0;
    reg [31:0] cap_addr=0,cap_data=0;
    reg cap_av=0,cap_wv=0,cap_br=0;
    wire cap_ar,cap_wr,cap_bv; wire [1:0] cap_bp;
    fpga_v8_capture_control_axil_arm_v2 capture_control (
        .clk(clk),.rst_n(rst_n),.config_valid(cfgv),.config_ready(cfgr),.config_generation(cfggen),
        .config_accept(cfga),.config_reject(cfgx),.epoch_start(epoch),.armed(armed),.config_ok(cfgok),
        .protocol_fault(lease_fault),.bank0_state(rawstate0),.bank1_state(rawstate1),
        .host_valid(1'b0),.host_src_addr(32'd0),.host_length(32'd0),.host_seq(32'd0),
        .host_generation(32'd0),.host_camera(3'd0),.host_bank(1'b0),.host_token(64'd0),
        .host_release_ready(1'b0),.host_release_accept(1'b0),.host_release_reject(1'b0),
        .published_count(pub_count),.failed_count(fail_count),.rejected_release_count(reject_count),
        .s_axil_awaddr(cap_addr),.s_axil_awprot(3'd0),.s_axil_awvalid(cap_av),.s_axil_awready(cap_ar),
        .s_axil_wdata(cap_data),.s_axil_wstrb(4'hf),.s_axil_wvalid(cap_wv),.s_axil_wready(cap_wr),
        .s_axil_bresp(cap_bp),.s_axil_bvalid(cap_bv),.s_axil_bready(cap_br),
        .s_axil_araddr(32'd0),.s_axil_arprot(3'd0),.s_axil_arvalid(1'b0),.s_axil_rready(1'b0)
    );
    fpga_v8_capture_lease #(.CAM_DATA_LEN(WORDS),.RAW_LENGTH(RAW_BYTES),
        .FRAME_WIDTH(WIDTH),.FRAME_HEIGHT(HEIGHT),.HOST_REQUIRED(1)) manager (
        .clk(clk),.rst(!rst_n),.config_valid(cfgv),.config_ready(cfgr),.config_generation(cfggen),
        .config_accept(cfga),.config_reject(cfgx),.epoch_start(epoch),.armed(armed),.config_ok(cfgok),
        .engine_idle(idle),.capture_bank(capture_bank),.admitted_sof(admit),
        .publish(publish),.publish_seq(pubseq),.retired_error(retired),.lease_block(lease_block),
        .bank0_state(rawstate0),.bank1_state(rawstate1),.protocol_fault(lease_fault),
        .input_valid(iv),.input_ready(ir),.input_raw_valid(rawvalid),.input_src_addr(ia),
        .input_length(il),.input_seq(iseq),.input_generation(igen),.input_camera(icam),
        .input_bank(ibank),.input_token(itoken),.release_valid(relv),.release_ready(relr),
        .release_camera(relcam),.release_bank(relbank),.release_seq(relseq),
        .release_generation(relgen),.release_token(reltoken),.release_accept(rela),.release_reject(relx),
        .host_valid(hv),.host_ready(hr),.host_src_addr(ha),.host_length(hl),
        .host_seq(hseq),.host_generation(hgen),.host_camera(hcam),.host_bank(hbank),.host_token(htoken),
        .host_release_valid(hrv),.host_release_ready(hrr),.host_release_camera(hrcam),
        .host_release_bank(hrbank),.host_release_seq(hrseq),.host_release_generation(hrgen),
        .host_release_token(hrtoken),.host_release_accept(hra),.host_release_reject(hrx),
        .published_count(pub_count),.failed_count(fail_count),.rejected_release_count(reject_count)
    );
    fpga_v8_capture_ov5640_ddr #(.CAM_DATA_LEN(WORDS)) camera (
        .axi_clk(clk),.axi_rst(!rst_n),.epoch_start(epoch),.lease_block(lease_block),
        .dma_abort(dma_abort),.dma_abort_req(abort_req),.dma_done(dma_done),.axi_data_available(credits),
        .axi_cam_en(1'b1),.s_data(pixel),.s_data_valid(pv),.s_hsync(1'b1),.s_vsync(sv),
        .axi_data(camera_data),.axi_data_valid(camera_dvalid),.axi_data_last(),.axi_data_ready(camera_dready),
        .axi_cmd_addr(cmd_addr),.axi_cmd_len(cmd_len),.axi_cmd_valid(cmd_valid),.axi_cmd_ready(cmd_ready),
        .xdma_req(legacy_req),.xdma_ack(legacy_ack),.admitted_sof(admit),.capture_bank(capture_bank),
        .publish(publish),.publish_seq(pubseq),.retired_error(retired),.engine_idle(idle),
        .capture_flush_o(flush),.frame_good_o(good),.capture_overflow_o(overflow),
        .dbg_fault_snapshot(),.dbg_reject_counts(),.dbg_input_pixels(),.dbg_axi_cnt(),.dbg_axi_num(),
        .dbg_zdin(),.dbg_zout(),.dbg_state(ctrl_state),.dbg_last_cnt(last_cnt),.dbg_wd_cnt()
    );
    wire [23:0] c_awid,c_bid;
    wire [191:0] c_awaddr;
    wire [47:0] c_awlen;
    wire [17:0] c_awsize,c_awprot;
    wire [11:0] c_awburst,c_bresp;
    wire [23:0] c_awcache;
    wire [5:0] c_awvalid,c_awready,c_wvalid,c_wready,c_wlast,c_bvalid,c_bready;
    wire [767:0] c_wdata;
    wire [95:0] c_wstrb;
    axi_dma_write #(.WAIT_FOR_DATA(1),.BURST_LEN(16),.WD_LIMIT(24'hffffff)) dma (
        .clk(clk),.rst(!rst_n),.cmd_valid(cmd_valid),.cmd_addr(cmd_addr),.cmd_len(cmd_len),
        .cmd_id(4'd3),.cmd_ready(cmd_ready),.data_in_available(credits),.abort_req(abort_req),
        .data_in_abort(dma_abort),.data_in(camera_data),.data_in_keep(16'hffff),
        .data_in_valid(camera_dvalid),.data_in_last(dma_done),.data_in_ready(camera_dready),
        .m_axi_awid(c_awid[16+:4]),.m_axi_awaddr(c_awaddr[128+:32]),
        .m_axi_awlen(c_awlen[32+:8]),.m_axi_awsize(c_awsize[12+:3]),
        .m_axi_awburst(c_awburst[8+:2]),.m_axi_awlock(),.m_axi_awcache(c_awcache[16+:4]),
        .m_axi_awprot(c_awprot[12+:3]),.m_axi_awvalid(c_awvalid[4]),.m_axi_awready(c_awready[4]),
        .m_axi_wdata(c_wdata[512+:128]),.m_axi_wstrb(c_wstrb[64+:16]),.m_axi_wlast(c_wlast[4]),
        .m_axi_wvalid(c_wvalid[4]),.m_axi_wready(c_wready[4]),.m_axi_bid(c_bid[16+:4]),
        .m_axi_bresp(c_bresp[8+:2]),.m_axi_bvalid(c_bvalid[4]),.m_axi_bready(c_bready[4])
    );
    reg dummy_enable=0;
    integer dummy_completed=0;
    function automatic [127:0] competitor_word(input integer owner,tx,beat);
        integer lane;
        for(lane=0;lane<16;lane=lane+1)competitor_word[lane*8+:8]=(owner*37+tx*19+beat*11+lane*7)&255;
    endfunction
    genvar gi;
    generate for(gi=0;gi<6;gi=gi+1) begin: writers
        if(gi!=4) begin: competitor
            reg [1:0] phase=0;
            integer tx=0, beat=0, gap=0;
            assign c_awid[gi*4+:4]=gi+8;
            assign c_awaddr[gi*32+:32]=32'h00800000+gi*32'h00100000+tx*256;
            assign c_awlen[gi*8+:8]=15;
            assign c_awsize[gi*3+:3]=4;
            assign c_awburst[gi*2+:2]=1;
            assign c_awcache[gi*4+:4]=3;
            assign c_awprot[gi*3+:3]=0;
            assign c_awvalid[gi]=dummy_enable && phase==0 && tx<CAMERA_BURSTS && gap==0;
            assign c_wdata[gi*128+:128]=competitor_word(gi,tx,beat);
            assign c_wstrb[gi*16+:16]=16'hffff;
            assign c_wlast[gi]=beat==15;
            assign c_wvalid[gi]=phase==1;
            assign c_bready[gi]=phase==2;
            always @(posedge clk) begin
                if(!rst_n) begin phase<=0;tx<=0;beat<=0;gap<=0;end
                else begin
                    if(gap>0)gap<=gap-1;
                    if(c_awvalid[gi]&&c_awready[gi])begin phase<=1;beat<=0;end
                    if(c_wvalid[gi]&&c_wready[gi])begin
                        if(beat==15)phase<=2;else beat<=beat+1;
                    end
                    if(c_bvalid[gi]&&c_bready[gi])begin
                        if(c_bid[gi*4+:4]!==gi+8||c_bresp[gi*2+:2]!==0) $fatal(1,"competitor B routing");
                        phase<=0;tx<=tx+1;gap<=64+gi*11;
                    end
                end
            end
        end
    end endgenerate
    wire core_busy,bridge_busy,bridge_done,bridge_error,bridge_cmd_error,arb_busy,arb_error;
    wire [2:0] arb_owner;
    wire [4:0] arb_flags;
    wire [1:0] outstate0,outstate1;
    reg [31:0] ax_awaddr=0,ax_wdata=0,ax_araddr=0;
    reg ax_awvalid=0,ax_wvalid=0,ax_bready=0,ax_arvalid=0,ax_rready=0;
    wire ax_awready,ax_wready,ax_bvalid,ax_arready,ax_rvalid;
    wire [1:0] ax_bresp,ax_rresp;
    wire [31:0] ax_rdata;
    wire [3:0] core_arid;
    wire [31:0] core_araddr;
    wire [7:0] core_arlen;
    wire [2:0] core_arsize;
    wire [1:0] core_arburst;
    wire core_arvalid,core_arready,core_rready;
    wire [3:0] awid,bid;
    wire [31:0] awaddr;
    wire [7:0] awlen;
    wire [2:0] awsize;
    wire [1:0] awburst,bresp;
    wire awvalid,awready,wvalid,wready,wlast,bvalid,bready;
    wire [127:0] wdata;
    wire [15:0] wstrb;
    wire [11:0] s_rid;
    wire [383:0] s_rdata;
    wire [5:0] s_rresp;
    wire [2:0] s_rvalid,s_rlast,s_arready;
    fpga_v8_cooperative_core #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.OUT_HEIGHT(OUT_HEIGHT),.TOP_ROWS(TOP_ROWS)) core (
        .core_clk(clk),.rst_n(rst_n),.input_valid(iv),.input_ready(ir),.input_raw_valid(rawvalid),
        .input_src_addr(ia),.input_source_seq(iseq),.input_generation(igen),.input_camera(icam),
        .input_camera_bank(ibank),.input_lease_token(itoken),.input_claim(input_claim),.input_reject(input_reject),
        .src_release_valid(relv),.src_release_ready(relr),.src_release_addr(reladdr),
        .src_release_seq(relseq),.src_release_generation(relgen),.src_release_camera(relcam),
        .src_release_camera_bank(relbank),.src_release_token(reltoken),.busy(core_busy),
        .bank0_state(outstate0),.bank1_state(outstate1),.bridge_busy(bridge_busy),.bridge_done(bridge_done),
        .bridge_error(bridge_error),.bridge_cmd_error(bridge_cmd_error),.arbiter_busy(arb_busy),
        .arbiter_owner(arb_owner),.arbiter_error(arb_error),.arbiter_error_flags(arb_flags),
        .s_axil_awaddr(ax_awaddr),.s_axil_awprot(3'd0),.s_axil_awvalid(ax_awvalid),.s_axil_awready(ax_awready),
        .s_axil_wdata(ax_wdata),.s_axil_wstrb(4'hf),.s_axil_wvalid(ax_wvalid),.s_axil_wready(ax_wready),
        .s_axil_bresp(ax_bresp),.s_axil_bvalid(ax_bvalid),.s_axil_bready(ax_bready),
        .s_axil_araddr(ax_araddr),.s_axil_arprot(3'd0),.s_axil_arvalid(ax_arvalid),.s_axil_arready(ax_arready),
        .s_axil_rdata(ax_rdata),.s_axil_rresp(ax_rresp),.s_axil_rvalid(ax_rvalid),.s_axil_rready(ax_rready),
        .camera_awid(c_awid),.camera_awaddr(c_awaddr),.camera_awlen(c_awlen),.camera_awsize(c_awsize),
        .camera_awburst(c_awburst),.camera_awlock(6'd0),.camera_awcache(c_awcache),.camera_awprot(c_awprot),
        .camera_awqos(24'd0),.camera_awregion(24'd0),.camera_awvalid(c_awvalid),.camera_awready(c_awready),
        .camera_wdata(c_wdata),.camera_wstrb(c_wstrb),.camera_wlast(c_wlast),.camera_wvalid(c_wvalid),
        .camera_wready(c_wready),.camera_bid(c_bid),.camera_bresp(c_bresp),.camera_bvalid(c_bvalid),.camera_bready(c_bready),
        .m_axi_read_arid(core_arid),.m_axi_read_araddr(core_araddr),.m_axi_read_arlen(core_arlen),
        .m_axi_read_arsize(core_arsize),.m_axi_read_arburst(core_arburst),.m_axi_read_arlock(),
        .m_axi_read_arcache(),.m_axi_read_arprot(),.m_axi_read_arqos(),.m_axi_read_arregion(),
        .m_axi_read_arvalid(core_arvalid),.m_axi_read_arready(core_arready),.m_axi_read_rid(s_rid[8+:4]),
        .m_axi_read_rdata(s_rdata[256+:128]),.m_axi_read_rresp(s_rresp[4+:2]),
        .m_axi_read_rlast(s_rlast[2]),.m_axi_read_rvalid(s_rvalid[2]),.m_axi_read_rready(core_rready),
        .m_axi_write_awid(awid),.m_axi_write_awaddr(awaddr),.m_axi_write_awlen(awlen),.m_axi_write_awsize(awsize),
        .m_axi_write_awburst(awburst),.m_axi_write_awlock(),.m_axi_write_awcache(),.m_axi_write_awprot(),
        .m_axi_write_awqos(),.m_axi_write_awregion(),.m_axi_write_awvalid(awvalid),.m_axi_write_awready(awready),
        .m_axi_write_wdata(wdata),.m_axi_write_wstrb(wstrb),.m_axi_write_wlast(wlast),.m_axi_write_wvalid(wvalid),
        .m_axi_write_wready(wready),.m_axi_write_bid(bid),.m_axi_write_bresp(bresp),.m_axi_write_bvalid(bvalid),.m_axi_write_bready(bready)
    );
    reg [31:0] host_araddr=0;
    reg [7:0] host_arlen=0;
    reg host_arvalid=0,host_rready=0;
    wire [6:0] arid,rid;
    wire [31:0] araddr;
    wire [7:0] arlen;
    wire [2:0] arsize;
    wire [1:0] arburst,rresp;
    wire arvalid,arready,rvalid,rlast,rready;
    wire [127:0] rdata;
    assign core_arready=s_arready[2];
    axi_crossbar_rd #(.S_COUNT(3),.M_COUNT(1),.DATA_WIDTH(128),.S_ID_WIDTH(4),.M_ID_WIDTH(7),
        .M_BASE_ADDR(32'd0),.M_ADDR_WIDTH(32'd28),.M_CONNECT(3'b101),.M_ISSUE(32'd1),
        .S_THREADS({3{32'd1}}),.S_ACCEPT({3{32'd1}}),
        .S_AR_REG_TYPE(6'd0),.S_R_REG_TYPE(6'd0),.M_AR_REG_TYPE(2'd0),.M_R_REG_TYPE(2'd0)) read_fabric (
        .clk(clk),.rst(!rst_n),.s_axi_arid({core_arid,4'd0,4'd6}),
        .s_axi_araddr({core_araddr,32'd0,host_araddr}),.s_axi_arlen({core_arlen,8'd0,host_arlen}),
        .s_axi_arsize({core_arsize,3'd4,3'd4}),.s_axi_arburst({core_arburst,2'd1,2'd1}),
        .s_axi_arlock(3'd0),.s_axi_arcache(12'd0),.s_axi_arprot(9'd0),.s_axi_arqos(12'd0),
        .s_axi_aruser(3'd0),.s_axi_arvalid({core_arvalid,1'b0,host_arvalid}),.s_axi_arready(s_arready),
        .s_axi_rid(s_rid),.s_axi_rdata(s_rdata),.s_axi_rresp(s_rresp),.s_axi_rlast(s_rlast),
        .s_axi_ruser(),.s_axi_rvalid(s_rvalid),.s_axi_rready({core_rready,1'b0,host_rready}),
        .m_axi_arid(arid),.m_axi_araddr(araddr),.m_axi_arlen(arlen),.m_axi_arsize(arsize),
        .m_axi_arburst(arburst),.m_axi_arlock(),.m_axi_arcache(),.m_axi_arprot(),.m_axi_arqos(),
        .m_axi_arregion(),.m_axi_aruser(),.m_axi_arvalid(arvalid),.m_axi_arready(arready),
        .m_axi_rid(rid),.m_axi_rdata(rdata),.m_axi_rresp(rresp),.m_axi_rlast(rlast),
        .m_axi_ruser(1'b0),.m_axi_rvalid(rvalid),.m_axi_rready(rready)
    );
    wire [7:0] adapter_flags;
    wire [4:0] water;
    wire wf_full,wf_empty,rf_full,rf_empty,write_busy,read_busy;
    wire [3:0] v_awid,v_awlen,v_wid,v_arid,v_arlen,v_rid;
    wire [27:0] v_awaddr,v_araddr;
    wire v_awvalid,v_awready,v_wready,v_wlast,v_arvalid,v_arready,v_rvalid,v_rlast;
    wire [127:0] v_wdata,v_rdata;
    wire [15:0] v_wstrb;
    wire vendor_wactive,vendor_ractive;
    reg hold_aw=0,hold_w=0,hold_ar=0,hold_r=0;
    wire [31:0] vendor_writes,vendor_reads;
    fpga_v8_ddr_adapter adapter (
        .clk(clk),.rst_n(rst_n),.s_awid(awid),.s_awaddr(awaddr),.s_awlen(awlen),
        .s_awsize(awsize),.s_awburst(awburst),.s_awvalid(awvalid),.s_awready(awready),
        .s_wdata(wdata),.s_wstrb(wstrb),.s_wlast(wlast),.s_wvalid(wvalid),.s_wready(wready),
        .s_bid(bid),.s_bresp(bresp),.s_bvalid(bvalid),.s_bready(bready),
        .s_arid(arid),.s_araddr(araddr),.s_arlen(arlen),.s_arsize(arsize),.s_arburst(arburst),
        .s_arvalid(arvalid),.s_arready(arready),.s_rid(rid),.s_rdata(rdata),.s_rresp(rresp),
        .s_rlast(rlast),.s_rvalid(rvalid),.s_rready(rready),
        .v_awid(v_awid),.v_awaddr(v_awaddr),.v_awlen(v_awlen),.v_awvalid(v_awvalid),.v_awready(v_awready),
        .v_wdata(v_wdata),.v_wstrb(v_wstrb),.v_wready(v_wready),.v_wlast(v_wlast),.v_wid(v_wid),
        .v_arid(v_arid),.v_araddr(v_araddr),.v_arlen(v_arlen),.v_arvalid(v_arvalid),.v_arready(v_arready),
        .v_rid(v_rid),.v_rdata(v_rdata),.v_rlast(v_rlast),.v_rvalid(v_rvalid),
        .error_flags(adapter_flags),.write_water_level(water),.write_fifo_full(wf_full),.write_fifo_empty(wf_empty),
        .read_fifo_full(rf_full),.read_fifo_empty(rf_empty),.write_busy(write_busy),.read_busy(read_busy)
    );
    fpga_v8_capture_contract_memory memory_model (
        .clk(clk),.rst_n(rst_n),.awid(v_awid),.awaddr(v_awaddr),.awlen(v_awlen),
        .awvalid(v_awvalid),.awready(v_awready),.wdata(v_wdata),.wstrb(v_wstrb),
        .wready(v_wready),.wlast(v_wlast),.wid(v_wid),.arid(v_arid),.araddr(v_araddr),
        .arlen(v_arlen),.arvalid(v_arvalid),.arready(v_arready),.rid(v_rid),.rdata(v_rdata),
        .rlast(v_rlast),.rvalid(v_rvalid),.hold_aw(hold_aw),.hold_w(hold_w),.hold_ar(hold_ar),.hold_r(hold_r),
        .write_active(vendor_wactive),.read_active(vendor_ractive),.writes(vendor_writes),.reads(vendor_reads)
    );
    // Original top read route runs as a shadow on identical accepted ARs and
    // vendor responses. Compare all 133 FIFO bits plus retained route prefix.
    wire old_arready,old_varvalid,old_rvalid,old_rlast,old_full,old_empty,old_inflight;
    wire [3:0] old_varid,old_varlen;
    wire [27:0] old_varaddr;
    wire [6:0] old_rid;
    wire [127:0] old_rdata;
    fpga_v8_top_read_route_snapshot original_read_route (
        .clk(clk),.rst_n(rst_n),.arid(arid),.araddr(araddr),.arlen(arlen),
        .arvalid(arvalid&&arready),.arready(old_arready),.vendor_arid(old_varid),
        .vendor_araddr(old_varaddr),.vendor_arlen(old_varlen),.vendor_arvalid(old_varvalid),
        .vendor_arready(v_arready),.vendor_rid(v_rid),.vendor_rdata(v_rdata),
        .vendor_rlast(v_rlast),.vendor_rvalid(v_rvalid),.rid(old_rid),.rdata(old_rdata),
        .rlast(old_rlast),.rvalid(old_rvalid),.rready(rready&&rvalid),
        .full(old_full),.empty(old_empty),.rd_inflight(old_inflight)
    );
    integer trace,meta,cycle=0,source_seed=0,source_count=0;
    integer capture_writes=0,publish_total=0,core_claims=0,core_releases=0;
    integer host_claims=0,host_releases=0,host_rejects=0,completed=0,host_read_words=0;
    integer reset_count=0,drop_count=0,raw_copies=0,output_copies=0,checks=0;
    integer active_seed=0,read_remaining=0,front_read_addr=0,front_write_left=0,front_write_addr=0;
    reg [6:0] active_rid;
    reg [3:0] front_write_id;
    reg reset_seen=0,rheld=0,wheld=0,ivheld=0,hvheld=0;
    reg [137:0] held_read;
    reg [144:0] held_write;
    reg [196:0] held_input,held_host;
    wire [196:0] input_payload={rawvalid,ia,il,iseq,igen,icam,ibank,itoken};
    wire [196:0] host_payload={1'b1,ha,hl,hseq,hgen,hcam,hbank,htoken};
    reg frozen0=0,frozen1=0;
    reg [127:0] frozen_image0[0:WORDS],frozen_image1[0:WORDS];
    reg out_frozen0=0,out_frozen1=0,ax_bseen=0;
    reg [127:0] frozen_output0[0:OUT_WORDS-1],frozen_output1[0:OUT_WORDS-1];
    reg [31:0] observed_ax_addr,observed_ax_data;
    integer n;
    reg log_core_release,log_host_release;
    always @(posedge clk) begin
        cycle=cycle+1;
        log_core_release=0;log_host_release=0;
        if(!rst_n) begin
            if(!reset_seen) begin $fdisplay(trace,"RESET %0d",cycle);reset_count=reset_count+1;end
            reset_seen=1;frozen0=0;frozen1=0;out_frozen0=0;out_frozen1=0;ax_bseen=0;
            rheld=0;wheld=0;ivheld=0;hvheld=0;
            read_remaining=0;front_write_left=0;
        end else begin
            reset_seen=0;
            if(adapter_flags!==0||arb_error||bridge_error||bridge_cmd_error||lease_fault||input_reject)
                $fatal(1,"integration error adapter=%h arb=%h bridge=%b lease=%b",adapter_flags,arb_flags,bridge_error,lease_fault);
            if(overflow||dma_abort||retired||abort_req) $fatal(1,"quality failed in valid fixture capture");
            if(v_awvalid&&water<({1'b0,v_awlen}+5'd1)) $fatal(1,"vendor AW before full staging");
            if(v_wready&&wf_empty) $fatal(1,"unthrottleable W consumed empty actual FIFO");
            if(v_rvalid&&rf_full) $fatal(1,"unthrottleable R overflow actual FIFO");
            if(rvalid!==old_rvalid || (rvalid&&{rid,rdata,rlast}!=={old_rid,old_rdata,old_rlast}))
                $fatal(1,"original read-route shadow mismatch");
            if(rheld&&(!rvalid||{rid,rdata,rresp,rlast}!==held_read)) $fatal(1,"R route/data changed while stalled");
            if(wheld&&(!wvalid||{wdata,wstrb,wlast}!==held_write)) $fatal(1,"fabric W changed while stalled");
            if(ivheld&&(!iv||input_payload!==held_input)) $fatal(1,"RAW descriptor changed under core backpressure");
            if(hvheld&&(!hv||host_payload!==held_host)) $fatal(1,"host RAW descriptor changed while stalled");
            rheld=rvalid&&!rready;held_read={rid,rdata,rresp,rlast};
            wheld=wvalid&&!wready;held_write={wdata,wstrb,wlast};
            ivheld=iv&&!ir;held_input=input_payload;
            hvheld=hv&&!hr;held_host=host_payload;
            if(ax_awvalid&&ax_awready)observed_ax_addr=ax_awaddr;
            if(ax_wvalid&&ax_wready)observed_ax_data=ax_wdata;
            if(admit) begin active_seed=source_seed;$fdisplay(trace,"ADMIT %0d %0d %0d",capture_bank,source_seed,cfggen);end
            if(publish) begin
                publish_total=publish_total+1;
                if(!good||ctrl_state!==6) $fatal(1,"publish before good actual tag B");
                if(capture_bank==0)begin
                    frozen0=1;
                    for(n=0;n<=WORDS;n=n+1) frozen_image0[n]=memory_model.get_word(B0+n*16);
                end else begin
                    frozen1=1;
                    for(n=0;n<=WORDS;n=n+1) frozen_image1[n]=memory_model.get_word(B1+n*16);
                end
                memory_model.dump(capture_bank?B1:B0,RAW_BYTES+16,
                    $sformatf("g%0d_s%0d_completed_raw.bin",cfggen,pubseq));
                $fdisplay(trace,"PUBLISH %0d %0d %0d %0d",capture_bank,pubseq,cfggen,active_seed);
            end
            if(input_claim) begin
                core_claims=core_claims+1;
                $fdisplay(trace,"COOP_CLAIM %0d %0d %0d %016h",ibank,iseq,igen,itoken);
            end
            if(hv&&hr)begin
                host_claims=host_claims+1;
                $fdisplay(trace,"RAW_CLAIM %0d %0d %0d %016h",hbank,hseq,hgen,htoken);
            end
            if(relv&&relr)begin
                if(reladdr!==(relbank?B1:B0)||relcam!==4) $fatal(1,"core source release layout/key");
                log_core_release=1;
            end
            if(hrv&&hrr)log_host_release=1;
            if(bridge_done)begin completed=completed+1;$fdisplay(trace,"DONE");end
            if(awvalid&&awready)begin
                if(front_write_left!=0) $fatal(1,"front AW overlap");
                front_write_addr=awaddr;front_write_left=awlen+1;front_write_id=awid;
                $fdisplay(trace,"AW %08h %0d %0d",awaddr,awid,awlen+1);
                if(awid==1&&((awaddr>=O0&&awaddr<O0+OUT_BYTES&&outstate0>=2)||
                             (awaddr>=O1&&awaddr<O1+OUT_BYTES&&outstate1>=2)))
                    $fatal(1,"bridge AW targets retained output lease");
                if(awid==3)capture_writes=capture_writes+1;
            end
            if(wvalid&&wready)begin
                if($isunknown({wdata,wstrb,wlast})||front_write_left<=0||wlast!==(front_write_left==1))
                    $fatal(1,"front complete W X/Z/obligation/last id=%0d word=%h strobe=%h last=%b left=%0d",front_write_id,wdata,wstrb,wlast,front_write_left);
                $fdisplay(trace,"W %08h %0d %032h %04h %0d",front_write_addr,front_write_id,wdata,wstrb,wlast);
                front_write_addr=front_write_addr+16;front_write_left=front_write_left-1;
            end
            if(bvalid&&bready) $fdisplay(trace,"B %0d %0d",bid,bresp);
            if(arvalid&&arready)begin
                if(read_remaining!=0) $fatal(1,"read route ownership changed before final consumed R");
                read_remaining=arlen+1;front_read_addr=araddr;active_rid=arid;
                if(arid!==7'h21&&arid!==7'h06) $fatal(1,"wrong full core/host read route ID");
                $fdisplay(trace,"AR %08h %02h %0d",araddr,arid,arlen+1);
            end
            if(rvalid&&rready)begin
                if($isunknown({rdata,rid,rlast,rresp})||rid!==active_rid||rresp!==0||read_remaining<=0||rlast!==(read_remaining==1))
                    $fatal(1,"complete R unknown/ID/route/last");
                $fdisplay(trace,"R %08h %02h %032h %0d",front_read_addr,rid,rdata,rlast);
                front_read_addr=front_read_addr+16;read_remaining=read_remaining-1;
            end
            if(v_wready)begin
                if(frozen0&&v_awaddr>=B0&&v_awaddr<B0+RAW_BYTES+16) $fatal(1,"vendor W targets frozen RAW bank0");
                if(frozen1&&v_awaddr>=B1&&v_awaddr<B1+RAW_BYTES+16) $fatal(1,"vendor W targets frozen RAW bank1");
            end
        end
        #1;
        if(rst_n&&ax_bvalid&&!ax_bseen)
            $fdisplay(trace,"AX_COMMIT %08h %08h %0d",observed_ax_addr,observed_ax_data,ax_bresp);
        ax_bseen=ax_bvalid;
        if(log_core_release)begin
            if(!rela||relx) $fatal(1,"real core release rejected");
            core_releases=core_releases+1;
            $fdisplay(trace,"COOP_RELEASE %0d %0d %0d %016h",relbank,relseq,relgen,reltoken);
        end
        if(log_host_release)begin
            if(hra)host_releases=host_releases+1;else host_rejects=host_rejects+1;
            $fdisplay(trace,"RAW_RELEASE %0d %0d %0d %016h %0d %0d",hrbank,hrseq,hrgen,hrtoken,hra,hrx);
        end
        if(rst_n)begin
            if(rawstate0==0) frozen0=0;
            if(rawstate1==0) frozen1=0;
            if(outstate0>=2&&!out_frozen0)begin
                out_frozen0=1;
                for(n=0;n<OUT_WORDS;n=n+1) frozen_output0[n]=memory_model.get_word(O0+n*16);
            end
            if(outstate1>=2&&!out_frozen1)begin
                out_frozen1=1;
                for(n=0;n<OUT_WORDS;n=n+1) frozen_output1[n]=memory_model.get_word(O1+n*16);
            end
            if(outstate0==0)out_frozen0=0;
            if(outstate1==0)out_frozen1=0;
        end
    end
    function automatic [15:0] fixture(input integer seed,index);
        integer x,y,r,g,b;
        begin
            x=index%WIDTH;y=index/WIDTH;
            r=(index*7+seed*3+y)%32;g=(index*11+seed*5+x)%64;b=(index*13+seed*9+y*3)%32;
            fixture=(r<<11)|(g<<5)|b;
        end
    endfunction
    task automatic tick(input integer cycles);repeat(cycles)@(negedge clk);endtask
    task automatic wait_camera_idle;begin wait(idle);tick(8);end endtask
    task automatic capture_write(input [31:0] address,value);
        begin
            @(negedge clk); cap_addr=address;cap_data=value;cap_av=1;cap_wv=1;
            @(posedge clk); if(!cap_ar||!cap_wr)$fatal(1,"capture holding slots unavailable");
            @(negedge clk);cap_av=0;cap_wv=0;
            // Every ARM races a real camera SOF on the committed request edge.
            if(address==32'h110)begin
                sv=1;#1;if(!cfgv||admit)$fatal(1,"ARM priority over actual SOF");
            end
            wait(cap_bv); if(cap_bp!==0)$fatal(1,"capture ARM B reject");
            @(negedge clk);sv=0;cap_br=1;@(negedge clk);cap_br=0;
        end
    endtask
    task automatic arm(input integer generation);
        begin
            wait_camera_idle();capture_write(32'h10c,generation);
            capture_write(32'h110,1);
            $fdisplay(trace,"ARM %0d",generation);
            wait_camera_idle();checks=checks+1;
        end
    endtask
    task automatic send_frame(input integer seed,input integer count);
        integer i;
        begin
            @(negedge clk);source_seed=seed;source_count=count;
            $fdisplay(trace,"FRAME %0d %0d",seed,count);
            sv=1;tick(6);sv=0;tick(6);
            for(i=0;i<count;i=i+1)begin
                pv=1;pixel=fixture(seed,i);@(negedge clk);
                // Continuous row pixels, fixed blanking, never sample ready.
                if(i%WIDTH==WIDTH-1)begin pv=0;tick(WIDTH>=640?512:64);end
            end
            pv=0;
        end
    endtask
    task automatic wait_publication(input integer seq);
        begin wait(last_cnt==seq);wait_camera_idle();checks=checks+1;end
    endtask
    task automatic claim_raw(input integer bank_id,seq,generation);
        begin
            wait(hv);
            if(hbank!==bank_id||hseq!==seq||hgen!==generation||ha!==(bank_id?B1:B0)||hl!==RAW_BYTES||hcam!==4||htoken!=={32'(generation),32'(seq)})
                $fatal(1,"RAW native claim identity");
            @(negedge clk);hr=1;@(negedge clk);hr=0;checks=checks+1;
        end
    endtask
    task automatic release_raw(input integer bank_id,seq,generation,accepted);
        begin
            @(negedge clk);hrbank=bank_id;hrseq=seq;hrgen=generation;
            hrtoken={32'(generation),32'(seq)};hrcam=4;hrv=1;
            @(posedge clk);#2;
            if(hra!==(accepted!=0)||hrx!==(accepted==0)) $fatal(1,"RAW release outcome");
            @(negedge clk);hrv=0;checks=checks+1;
        end
    endtask
    task automatic check_frozen;
        integer i;
        begin
            for(i=0;i<=WORDS;i=i+1)begin
                if(frozen0&&memory_model.get_word(B0+i*16)!==frozen_image0[i]) $fatal(1,"frozen RAW0 changed");
                if(frozen1&&memory_model.get_word(B1+i*16)!==frozen_image1[i]) $fatal(1,"frozen RAW1 changed");
            end
            for(i=0;i<OUT_WORDS;i=i+1)begin
                if(out_frozen0&&memory_model.get_word(O0+i*16)!==frozen_output0[i]) $fatal(1,"frozen output0 changed");
                if(out_frozen1&&memory_model.get_word(O1+i*16)!==frozen_output1[i]) $fatal(1,"frozen output1 changed");
            end
            $fdisplay(trace,"FROZEN %0d %0d",frozen0,frozen1);checks=checks+1;
        end
    endtask
    task automatic drop_frame(input integer seed);
        integer before_aw,before_publish;
        begin
            before_aw=capture_writes;before_publish=publish_total;
            send_frame(seed,WIDTH*HEIGHT);tick(30);
            if(capture_writes!=before_aw||publish_total!=before_publish) $fatal(1,"blocked sensor frame wrote RAW DDR");
            check_frozen();$fdisplay(trace,"DROP %0d",seed);drop_count=drop_count+1;
        end
    endtask
    task automatic ax_write(input [31:0] address,value,input [1:0] expected);
        reg adone,wdone;
        begin
            @(negedge clk);ax_awaddr=address;ax_wdata=value;ax_awvalid=1;ax_wvalid=1;adone=0;wdone=0;
            while(!adone||!wdone)begin
                @(posedge clk);
                if(ax_awvalid&&ax_awready)adone=1;
                if(ax_wvalid&&ax_wready)wdone=1;
                @(negedge clk);if(adone)ax_awvalid=0;if(wdone)ax_wvalid=0;
            end
            wait(ax_bvalid);tick(3);
            if(ax_bresp!==expected) $fatal(1,"AXIL write %h response %h",address,ax_bresp);
            ax_bready=1;@(negedge clk);ax_bready=0;
            $fdisplay(trace,"AXW %08h %08h %0d",address,value,expected);
        end
    endtask
    task automatic ax_read(input [31:0] address,output [31:0] value);
        begin
            @(negedge clk);ax_araddr=address;ax_arvalid=1;
            do @(posedge clk);while(!ax_arready);
            @(negedge clk);ax_arvalid=0;wait(ax_rvalid);tick(2);
            if(ax_rresp!==0) $fatal(1,"AXIL read response");
            value=ax_rdata;ax_rready=1;@(negedge clk);ax_rready=0;
            $fdisplay(trace,"AXR %08h %08h",address,value);
        end
    endtask
    task automatic ddr_copy(input integer address,bytes,input string name);
        integer offset,beats,i,lane,stream;
        reg [127:0] word;
        begin
            stream=$fopen(name,"wb");offset=0;
            while(offset<bytes)begin
                beats=((bytes-offset+15)/16>16)?16:(bytes-offset+15)/16;
                @(negedge clk);host_araddr=address+offset;host_arlen=beats-1;host_arvalid=1;
                do @(posedge clk);while(!s_arready[0]);
                @(negedge clk);host_arvalid=0;
                // Hold until vendor has emitted the full nonbackpressurable
                // burst; the actual FIFO safely stores all 16 words.
                wait(!vendor_ractive&&!v_rvalid&&rvalid);tick(7);
                for(i=0;i<beats;i=i+1)begin
                    host_rready=0;wait(s_rvalid[0]);tick(1+i%3);
                    word=s_rdata[0+:128];
                    if(s_rid[0+:4]!==6||s_rresp[0+:2]!==0||s_rlast[0]!==(i==beats-1)||$isunknown(word))
                        $fatal(1,"host complete DDR word/route/last");
                    for(lane=0;lane<16;lane=lane+1)
                        if(offset+i*16+lane<bytes) $fwrite(stream,"%c",word[lane*8+:8]);
                    host_rready=1;@(posedge clk);@(negedge clk);host_rready=0;host_read_words=host_read_words+1;
                end
                offset=offset+beats*16;
            end
            $fclose(stream);tick(3);
        end
    endtask
    task automatic copy_raw(input integer bank_id,seq,generation,seed);
        string prefix;
        begin
            prefix=$sformatf("g%0d_s%0d",generation,seq);
            ddr_copy(bank_id?B1:B0,RAW_BYTES+16,{prefix,"_rawbankcopy.bin"});
            $fdisplay(trace,"RAW_COPY %0d %0d %0d",bank_id,seq,generation);
            $fdisplay(meta,"RAW %0d %0d %0d %0d %016h %s_rawbankcopy.bin %s_completed_raw.bin",
                seq,generation,seed,bank_id,{32'(generation),32'(seq)},prefix,prefix);
            raw_copies=raw_copies+1;check_frozen();
        end
    endtask
    task automatic copy_output(input integer bank_id,seq,generation,raw_bank);
        reg [31:0] value;
        string prefix;
        begin
            prefix=$sformatf("g%0d_s%0d",generation,seq);
            ax_read('h0c,value);if(value!==bank_id) $fatal(1,"output ready order");
            ax_write('h30,bank_id,0);
            ax_read('h10,value);if(value!==bank_id) $fatal(1,"bound output bank");
            ax_read('h14,value);if(value!==seq) $fatal(1,"bound sequence");
            ax_read('h18,value);if(value!==generation) $fatal(1,"bound generation");
            ax_read('h1c,value);if(value!==OUT_BYTES) $fatal(1,"bound length");
            ax_read('h20,value);if(value!==(bank_id?O1:O0)) $fatal(1,"bound output address");
            ax_read('h24,value);if(value!==4) $fatal(1,"bound camera index");
            ax_read('h28,value);if(value!==raw_bank) $fatal(1,"bound RAW bank");
            ax_read('h2c,value);if(value!==(raw_bank?B1:B0)) $fatal(1,"bound RAW address");
            ax_read('h34,value);if(value!==seq) $fatal(1,"bound token low");
            ax_read('h38,value);if(value!==generation) $fatal(1,"bound token high");
            $fdisplay(trace,"OUTPUT_CLAIM %0d %0d %0d",bank_id,seq,generation);
            ddr_copy(bank_id?O1:O0,OUT_BYTES,{prefix,"_preparedinput.bin"});
            $fdisplay(trace,"OUTPUT_COPY %0d %0d %0d",bank_id,seq,generation);
            $fdisplay(meta,"OUTPUT %0d %0d %0d %s_preparedinput.bin",seq,generation,bank_id,prefix);
            // Stale generation cannot ACK the actual bound output claim.
            ax_write('h40,bank_id,0);ax_write('h44,seq,0);ax_write('h48,generation-1,0);ax_write('h4c,1,2);
            ax_write('h48,generation,0);ax_write('h4c,1,0);
            $fdisplay(trace,"OUTPUT_ACK %0d %0d %0d",bank_id,seq,generation);
            output_copies=output_copies+1;checks=checks+1;
        end
    endtask
    task automatic common_reset;
        begin
            @(negedge clk);rst_n=0;cap_av=0;cap_wv=0;cap_br=0;sv=0;pv=0;hr=0;hrv=0;dummy_enable=0;
            host_arvalid=0;host_rready=0;ax_awvalid=0;ax_wvalid=0;ax_bready=0;ax_arvalid=0;ax_rready=0;
            hold_aw=0;hold_w=0;hold_ar=0;hold_r=0;legacy_ack=0;
            tick(8);rst_n=1;wait_camera_idle();
        end
    endtask
    initial begin
        trace=$fopen("contract_trace.txt","w");meta=$fopen("frames.txt","w");
        common_reset();arm(101);dummy_enable=1;
        send_frame(1,WIDTH*HEIGHT);wait_publication(1);claim_raw(0,1,101);
        // Host RAW read competes with actual bridge AR traffic while converting.
        copy_raw(0,1,101,1);
        wait(core_releases==1);tick(10);
        if(rawstate0!==2) $fatal(1,"core release cleared host-held RAW lease");
        check_frozen();
        if(MODE==0)begin
            send_frame(2,WIDTH*HEIGHT);wait_publication(2);claim_raw(1,2,101);copy_raw(1,2,101,2);
            wait(core_releases==2);tick(10);
            if(outstate0!==2||outstate1!==2||rawstate0!==2||rawstate1!==2) $fatal(1,"two independently held source/output banks");
            drop_frame(90);
            release_raw(0,1,101,1);
            // No output ACK: next camera bank is captured and offered, but the
            // core has no free output and cannot claim this RAW descriptor.
            send_frame(3,WIDTH*HEIGHT);wait_publication(3);claim_raw(0,3,101);copy_raw(0,3,101,3);
            if(!iv||ir||core_claims!=2) $fatal(1,"output ownership failed to backpressure new RAW");
            release_raw(1,2,101,1);
            send_frame(4,WIDTH*HEIGHT);wait_publication(4);claim_raw(1,4,101);copy_raw(1,4,101,4);
            drop_frame(91);release_raw(0,3,101,1);tick(20);
            if(rawstate0!==2||core_claims!=2) $fatal(1,"host-only release cleared unclaimed core obligation");
            drop_frame(92);
            legacy_ack=3;tick(3);legacy_ack=0;release_raw(0,1,101,0);check_frozen();
            copy_output(0,1,101,0);
            wait(core_claims==3);wait(core_releases==3);tick(10);
            if(rawstate0!==0||rawstate1!==2) $fatal(1,"real core release after host release did not free exact source");
            copy_output(1,2,101,1);
            wait(core_releases==4);tick(10);
            if(rawstate1!==2) $fatal(1,"new source lost host lease after core completion");
            release_raw(1,4,101,1);
            copy_output(0,3,101,0);copy_output(1,4,101,1);
            // Fresh capture AFTER all earlier output ACKs: prove actual source
            // and output bank reuse with the next globally unique sequence.
            send_frame(5,WIDTH*HEIGHT);wait_publication(5);claim_raw(0,5,101);copy_raw(0,5,101,5);
            wait(core_releases==5);release_raw(0,5,101,1);copy_output(0,5,101,0);
        end else begin
            // Retain paired artifacts for the first completed frame, then
            // reset in a NEW busy bridge/camera operation after accepted AW.
            release_raw(0,1,101,1);copy_output(0,1,101,0);
            hold_r=1;
            send_frame(2,WIDTH*HEIGHT);wait_publication(2);claim_raw(1,2,101);
            // RAW copy can run after the emitted AR is unblocked briefly.
            hold_r=0;copy_raw(1,2,101,2);hold_r=1;
            wait(core_busy);hold_aw=1;
            send_frame(3,128);wait(write_busy);tick(8);
            if(!core_busy||!write_busy) $fatal(1,"reset did not hit accepted AW while core busy");
            $fdisplay(trace,"RESET_ACTIVE_AW");common_reset();
            // The cancelled source's paired output is explicitly unavailable.
            $fdisplay(meta,"CANCELLED 2 101 coordinated_reset");
            drop_frame(93);arm(102);dummy_enable=1;
            send_frame(5,WIDTH*HEIGHT);wait_publication(1);claim_raw(0,1,102);copy_raw(0,1,102,5);
            release_raw(0,1,101,0);
            wait(core_releases>=2);tick(10);check_frozen();release_raw(0,1,102,1);
            copy_output(0,1,102,0);
            send_frame(6,WIDTH*HEIGHT);wait_publication(2);claim_raw(1,2,102);copy_raw(1,2,102,6);
            wait(core_releases>=3);release_raw(1,2,102,1);copy_output(0,2,102,1);
        end
        wait_camera_idle();
        wait(!core_busy&&!arb_busy&&!write_busy&&!read_busy&&!vendor_wactive&&!vendor_ractive);
        tick(30);
        if(rawstate0||rawstate1||outstate0||outstate1||!wf_empty||!rf_empty||iv||hv||relv) $fatal(1,"final owned/buffered state");
        if(MODE==0&&core_claims!=5) $fatal(1,"missing actual bridge transactions");
        $fdisplay(trace,"FINISH %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",publish_total,core_claims,core_releases,
            host_claims,host_releases,host_rejects,completed,host_read_words,drop_count,raw_copies,output_copies);
        $fclose(meta);$fclose(trace);
        $display("CAPTURE_CORE_CONTRACT_PASS mode=%0d cycles=%0d publishes=%0d bridge_done=%0d raw_copies=%0d output_copies=%0d host_R_words=%0d vendor_W_words=%0d vendor_R_words=%0d checks=%0d",
            MODE,cycle,publish_total,completed,raw_copies,output_copies,host_read_words,vendor_writes,vendor_reads,checks);
        $finish;
    end
    initial begin repeat(25000000)@(posedge clk);$fatal(1,"contract timeout mode=%0d core=%b raw=%0d/%0d output=%0d/%0d pub=%0d",MODE,core_busy,rawstate0,rawstate1,outstate0,outstate1,publish_total);end
endmodule
