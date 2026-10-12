`timescale 1ns/1ps
// Reuses the read-only verified front-side core harness; replaces its DDR
// response drivers explicitly with the adapter and independent vendor stub.
module tb_core_ddr_adapter;
    parameter integer LEGACY_BID=0, MODE=4, WIDTH=640, HEIGHT=480, OUT_HEIGHT=640, TOP_ROWS=80, CAMERA_BURSTS=512;
    localparam integer SRC_BUS=(WIDTH*HEIGHT*2+15)/16*16;
    localparam integer OUT_BYTES=WIDTH*OUT_HEIGHT*3, OUT_BUS=(OUT_BYTES+15)/16*16;
    tb_fpga_v8_cooperative_core #(
        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.OUT_HEIGHT(OUT_HEIGHT),.TOP_ROWS(TOP_ROWS),
        .MODE(MODE),.CAMERA_BURSTS(CAMERA_BURSTS)
    ) front();
    wire awready,wready,bvalid,arready,rvalid,rlast;
    wire [3:0] bid;
    wire [1:0] bresp,rresp;
    wire [6:0] rid;
    wire [127:0] rdata;
    wire [7:0] flags;
    wire [4:0] water;
    wire wf_full,wf_empty,rf_full,rf_empty,wb,rb;
    wire [3:0] v_awid,v_awlen,v_wid,v_arid,v_arlen,v_rid;
    wire [27:0] v_awaddr,v_araddr;
    wire v_awvalid,v_awready,v_wready,v_wlast,v_arvalid,v_arready,v_rvalid,v_rlast;
    wire [127:0] v_wdata,v_rdata;
    wire [15:0] v_wstrb;
    wire vendor_wactive,vendor_ractive;
    wire [3:0] original_bid,original_minted_bid;
    fpga_v8_top_bid_snapshot original_broute (.minted_bid(bid),.arb_s_bid(original_bid),.observed_minted_bid(original_minted_bid));
    wire [3:0] routed_bid=LEGACY_BID?original_bid:bid;
    wire routed_awready=awready && !front.force_aw;
    wire routed_wready=wready && !front.force_w;
    wire routed_arready=arready && !front.force_ar;
    fpga_v8_ddr_adapter adapter (
        .clk(front.clk),.rst_n(front.rst_n),
        .s_awid(front.awid),.s_awaddr(front.awaddr),.s_awlen(front.awlen),
        .s_awsize(front.awsize),.s_awburst(front.awburst),.s_awvalid(front.awvalid && !front.force_aw),.s_awready(awready),
        .s_wdata(front.wdata),.s_wstrb(front.wstrb),.s_wlast(front.wlast),.s_wvalid(front.wvalid && !front.force_w),.s_wready(wready),
        .s_bid(bid),.s_bresp(bresp),.s_bvalid(bvalid),.s_bready(front.bready),
        .s_arid({3'b010,front.arid}),.s_araddr(front.araddr),.s_arlen(front.arlen),
        .s_arsize(front.arsize),.s_arburst(front.arburst),.s_arvalid(front.arvalid && !front.force_ar),.s_arready(arready),
        .s_rid(rid),.s_rdata(rdata),.s_rresp(rresp),.s_rlast(rlast),.s_rvalid(rvalid),.s_rready(front.rready),
        .v_awid(v_awid),.v_awaddr(v_awaddr),.v_awlen(v_awlen),.v_awvalid(v_awvalid),.v_awready(v_awready),
        .v_wdata(v_wdata),.v_wstrb(v_wstrb),.v_wready(v_wready),.v_wlast(v_wlast),.v_wid(v_wid),
        .v_arid(v_arid),.v_araddr(v_araddr),.v_arlen(v_arlen),.v_arvalid(v_arvalid),.v_arready(v_arready),
        .v_rid(v_rid),.v_rdata(v_rdata),.v_rlast(v_rlast),.v_rvalid(v_rvalid),
        .error_flags(flags),.write_water_level(water),.write_fifo_full(wf_full),.write_fifo_empty(wf_empty),
        .read_fifo_full(rf_full),.read_fifo_empty(rf_empty),.write_busy(wb),.read_busy(rb)
    );
    fpga_v8_vendor_ddr_stub #(.SRC_BUS(SRC_BUS),.OUT_BYTES(OUT_BYTES),.OUT_BUS(OUT_BUS),.CAMERA_BURSTS(CAMERA_BURSTS),.CORE_MEMORY(1)) vendor (
        .clk(front.clk),.rst_n(front.rst_n),
        .awid(v_awid),.awaddr(v_awaddr),.awlen(v_awlen),.awvalid(v_awvalid),.awready(v_awready),
        .wdata(v_wdata),.wstrb(v_wstrb),.wready(v_wready),.wlast(v_wlast),.wid(v_wid),
        .arid(v_arid),.araddr(v_araddr),.arlen(v_arlen),.arvalid(v_arvalid),.arready(v_arready),
        .rid(v_rid),.rdata(v_rdata),.rlast(v_rlast),.rvalid(v_rvalid),
        .hold_aw(front.force_aw),.hold_ar(front.force_ar),.hold_w(front.force_w),.hold_r(1'b0),
        .hold_final_output(front.hold_final_b),.write_active(vendor_wactive),.read_active(vendor_ractive),
        .consumed_words(),.emitted_words()
    );
    initial begin
        force front.awready=routed_awready; force front.wready=routed_wready;
        force front.bid=routed_bid; force front.bresp=bresp; force front.bvalid=bvalid;
        force front.arready=routed_arready; force front.rid=rid[3:0];
        force front.rdata=rdata; force front.rresp=rresp; force front.rlast=rlast; force front.rvalid=rvalid;
        if(LEGACY_BID) force front.cameras_enable=1'b0;
    end
    always @(posedge front.clk) if(front.rst_n) begin
        if(front.input_claim) vendor.load_source(front.input_source_seq);
        if(v_awvalid && water<({1'b0,v_awlen}+5'd1)) $fatal(1,"vendor AW before entire burst staged");
        if(v_wready && wf_empty) $fatal(1,"unthrottleable vendor consumed empty FIFO");
        if(v_rvalid && rf_full) $fatal(1,"unthrottleable vendor overflowed R FIFO");
        if(flags!==0) $fatal(1,"adapter diagnostics %02x",flags);
        if(rvalid && rid[6:4]!==3'b010) $fatal(1,"core S02 routing prefix lost");
    end
    initial begin
        if(LEGACY_BID) begin
            wait(front.arbiter_error_flags[1]);
            if(!front.bridge_error || bid!==4'd1 || routed_bid!==0) $fatal(1,"legacy BID mismatch not demonstrated");
            $display("ORIGINAL_BID_FAILURE_CONFIRMED accepted_awid=1 minted_bid=1 routed_bid=0 bridge_error=1 arbiter_id_error=1");
            $finish;
        end else begin
            wait(front.copied_bytes==((MODE==0)?3:1)*OUT_BYTES && front.bank0_state==0 && front.bank1_state==0 &&
                front.cam_state[0]==3 && front.cam_state[1]==3 && front.cam_state[2]==3 && front.cam_state[3]==3 && front.cam_state[4]==3 && front.cam_state[5]==3);
            repeat(2) @(negedge front.clk);
            if(vendor_wactive || vendor_ractive || wb || rb || !wf_empty || !rf_empty) $fatal(1,"adapter not drained at final core audit");
            vendor.audit_memory();
            $display("ADAPTER_CORE_PASS mode=%0d vendor_w_words=%0d vendor_r_words=%0d full_output_bytes=%0d",MODE,vendor.consumed_words,vendor.emitted_words,OUT_BYTES);
        end
    end
endmodule
