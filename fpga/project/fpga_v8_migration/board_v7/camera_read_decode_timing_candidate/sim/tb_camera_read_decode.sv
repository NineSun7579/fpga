`timescale 1ns/1ps
module camera_pair #(parameter AXI_ADDR_WIDTH=32, parameter BASE_ADDR=32'h20000000, parameter ID=0)(output reg done=0);
reg clk=0; always #5 clk=~clk;
reg  rst = 0;
reg  s_axi_awvalid = 0;
wire  ref_s_axi_awready, dut_s_axi_awready;
reg [AXI_ADDR_WIDTH-1 : 0] s_axi_awaddr = 0;
reg  s_axi_wvalid = 0;
wire  ref_s_axi_wready, dut_s_axi_wready;
reg [AXI_ADDR_WIDTH-1 : 0] s_axi_wdata = 0;
reg [AXI_ADDR_WIDTH/8-1 : 0] s_axi_wstrb = 0;
wire  ref_s_axi_bvalid, dut_s_axi_bvalid;
reg  s_axi_bready = 0;
wire [ 1 : 0] ref_s_axi_bresp, dut_s_axi_bresp;
reg  s_axi_arvalid = 0;
wire  ref_s_axi_arready, dut_s_axi_arready;
reg [AXI_ADDR_WIDTH-1 : 0] s_axi_araddr = 0;
wire  ref_s_axi_rvalid, dut_s_axi_rvalid;
reg  s_axi_rready = 0;
wire [AXI_ADDR_WIDTH-1 : 0] ref_s_axi_rdata, dut_s_axi_rdata;
wire [ 1 : 0] ref_s_axi_rresp, dut_s_axi_rresp;
wire [AXI_ADDR_WIDTH-1 : 0] ref_cam_addr_1, dut_cam_addr_1;
wire [AXI_ADDR_WIDTH-1 : 0] ref_cam_addr_2, dut_cam_addr_2;
wire [1 : 0] ref_xdma_ack, dut_xdma_ack;
wire  ref_cam_en, dut_cam_en;
wire [7:0] ref_dly_step, dut_dly_step;
reg [31:0] dbg_cdc_input = 0;
reg [31:0] dbg_cdc_output = 0;
reg [31:0] dbg_cdc_drop = 0;
reg [31:0] dbg_cdc_seq = 0;
reg [31:0] dbg_fault_snapshot = 0;
reg [31:0] dbg_reject_counts = 0;
reg [31:0] dbg_input_pixels = 0;
reg [31:0] dbg_vsync_widths = 0;
reg [31:0] dbg_cam_words = 0;
reg [31:0] dbg_vsyncs = 0;
reg [31:0] dbg_hsyncs = 0;
reg [31:0] dbg_href_raw = 0;
reg [31:0] dbg_vsync_raw = 0;
reg [31:0] dbg_beat_cnt = 0;
reg [31:0] dbg_beat_last = 0;
reg [31:0] dbg_cmd_cnt = 0;
reg [31:0] dbg_axi_sticky = 0;
reg [31:0] dbg_axi_stat = 0;
reg [31:0] dbg_b_cnt = 0;
reg [31:0] dbg_aw_cnt = 0;
reg [31:0] dbg_w_cnt = 0;
reg [31:0] dbg_axi_cnt = 0;
reg [31:0] dbg_zdin = 0;
reg [31:0] dbg_zout = 0;
reg [31:0] dbg_axi_num = 0;
reg [31:0] dbg_state = 0;
reg [31:0] dbg_last_cnt = 0;
reg [31:0] dbg_wd_cnt = 0;
reg [1:0] dbg_xdma_req = 0;
reg [31:0] dbg_i2c_status = 0;
reg [31:0] dbg_pclk_cnt = 0;
reg [31:0] dbg_sys_status = 0;
reg [31:0] dbg_clk_status = 0;
wire  ref_pt_req_toggle, dut_pt_req_toggle;
wire [15:0] ref_pt_addr, dut_pt_addr;
wire [ 7:0] ref_pt_wdata, dut_pt_wdata;
wire  ref_pt_rw, dut_pt_rw;
reg [ 7:0] pt_rdata = 0;
reg  pt_ack = 0;
reg  pt_done_toggle = 0;
ov5640_reg_reference #(.AXI_ADDR_WIDTH(AXI_ADDR_WIDTH), .BASE_ADDR(BASE_ADDR), .CAM_ADDR_1_DEF(32'h12345678), .CAM_ADDR_2_DEF(32'h87654321), .CAM_EN_DEF(0), .DLY_STEP_DEF(73)) ref_inst (
    .clk(clk),
    .rst(rst),
    .s_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(ref_s_axi_awready),
    .s_axi_awaddr(s_axi_awaddr),
    .s_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(ref_s_axi_wready),
    .s_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(s_axi_wstrb),
    .s_axi_bvalid(ref_s_axi_bvalid),
    .s_axi_bready(s_axi_bready),
    .s_axi_bresp(ref_s_axi_bresp),
    .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(ref_s_axi_arready),
    .s_axi_araddr(s_axi_araddr),
    .s_axi_rvalid(ref_s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
    .s_axi_rdata(ref_s_axi_rdata),
    .s_axi_rresp(ref_s_axi_rresp),
    .cam_addr_1(ref_cam_addr_1),
    .cam_addr_2(ref_cam_addr_2),
    .xdma_ack(ref_xdma_ack),
    .cam_en(ref_cam_en),
    .dly_step(ref_dly_step),
    .dbg_cdc_input(dbg_cdc_input),
    .dbg_cdc_output(dbg_cdc_output),
    .dbg_cdc_drop(dbg_cdc_drop),
    .dbg_cdc_seq(dbg_cdc_seq),
    .dbg_fault_snapshot(dbg_fault_snapshot),
    .dbg_reject_counts(dbg_reject_counts),
    .dbg_input_pixels(dbg_input_pixels),
    .dbg_vsync_widths(dbg_vsync_widths),
    .dbg_cam_words(dbg_cam_words),
    .dbg_vsyncs(dbg_vsyncs),
    .dbg_hsyncs(dbg_hsyncs),
    .dbg_href_raw(dbg_href_raw),
    .dbg_vsync_raw(dbg_vsync_raw),
    .dbg_beat_cnt(dbg_beat_cnt),
    .dbg_beat_last(dbg_beat_last),
    .dbg_cmd_cnt(dbg_cmd_cnt),
    .dbg_axi_sticky(dbg_axi_sticky),
    .dbg_axi_stat(dbg_axi_stat),
    .dbg_b_cnt(dbg_b_cnt),
    .dbg_aw_cnt(dbg_aw_cnt),
    .dbg_w_cnt(dbg_w_cnt),
    .dbg_axi_cnt(dbg_axi_cnt),
    .dbg_zdin(dbg_zdin),
    .dbg_zout(dbg_zout),
    .dbg_axi_num(dbg_axi_num),
    .dbg_state(dbg_state),
    .dbg_last_cnt(dbg_last_cnt),
    .dbg_wd_cnt(dbg_wd_cnt),
    .dbg_xdma_req(dbg_xdma_req),
    .dbg_i2c_status(dbg_i2c_status),
    .dbg_pclk_cnt(dbg_pclk_cnt),
    .dbg_sys_status(dbg_sys_status),
    .dbg_clk_status(dbg_clk_status),
    .pt_req_toggle(ref_pt_req_toggle),
    .pt_addr(ref_pt_addr),
    .pt_wdata(ref_pt_wdata),
    .pt_rw(ref_pt_rw),
    .pt_rdata(pt_rdata),
    .pt_ack(pt_ack),
    .pt_done_toggle(pt_done_toggle)
);
ov5640_reg_candidate #(.AXI_ADDR_WIDTH(AXI_ADDR_WIDTH), .BASE_ADDR(BASE_ADDR), .CAM_ADDR_1_DEF(32'h12345678), .CAM_ADDR_2_DEF(32'h87654321), .CAM_EN_DEF(0), .DLY_STEP_DEF(73)) dut_inst (
    .clk(clk),
    .rst(rst),
    .s_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(dut_s_axi_awready),
    .s_axi_awaddr(s_axi_awaddr),
    .s_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(dut_s_axi_wready),
    .s_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(s_axi_wstrb),
    .s_axi_bvalid(dut_s_axi_bvalid),
    .s_axi_bready(s_axi_bready),
    .s_axi_bresp(dut_s_axi_bresp),
    .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(dut_s_axi_arready),
    .s_axi_araddr(s_axi_araddr),
    .s_axi_rvalid(dut_s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
    .s_axi_rdata(dut_s_axi_rdata),
    .s_axi_rresp(dut_s_axi_rresp),
    .cam_addr_1(dut_cam_addr_1),
    .cam_addr_2(dut_cam_addr_2),
    .xdma_ack(dut_xdma_ack),
    .cam_en(dut_cam_en),
    .dly_step(dut_dly_step),
    .dbg_cdc_input(dbg_cdc_input),
    .dbg_cdc_output(dbg_cdc_output),
    .dbg_cdc_drop(dbg_cdc_drop),
    .dbg_cdc_seq(dbg_cdc_seq),
    .dbg_fault_snapshot(dbg_fault_snapshot),
    .dbg_reject_counts(dbg_reject_counts),
    .dbg_input_pixels(dbg_input_pixels),
    .dbg_vsync_widths(dbg_vsync_widths),
    .dbg_cam_words(dbg_cam_words),
    .dbg_vsyncs(dbg_vsyncs),
    .dbg_hsyncs(dbg_hsyncs),
    .dbg_href_raw(dbg_href_raw),
    .dbg_vsync_raw(dbg_vsync_raw),
    .dbg_beat_cnt(dbg_beat_cnt),
    .dbg_beat_last(dbg_beat_last),
    .dbg_cmd_cnt(dbg_cmd_cnt),
    .dbg_axi_sticky(dbg_axi_sticky),
    .dbg_axi_stat(dbg_axi_stat),
    .dbg_b_cnt(dbg_b_cnt),
    .dbg_aw_cnt(dbg_aw_cnt),
    .dbg_w_cnt(dbg_w_cnt),
    .dbg_axi_cnt(dbg_axi_cnt),
    .dbg_zdin(dbg_zdin),
    .dbg_zout(dbg_zout),
    .dbg_axi_num(dbg_axi_num),
    .dbg_state(dbg_state),
    .dbg_last_cnt(dbg_last_cnt),
    .dbg_wd_cnt(dbg_wd_cnt),
    .dbg_xdma_req(dbg_xdma_req),
    .dbg_i2c_status(dbg_i2c_status),
    .dbg_pclk_cnt(dbg_pclk_cnt),
    .dbg_sys_status(dbg_sys_status),
    .dbg_clk_status(dbg_clk_status),
    .pt_req_toggle(dut_pt_req_toggle),
    .pt_addr(dut_pt_addr),
    .pt_wdata(dut_pt_wdata),
    .pt_rw(dut_pt_rw),
    .pt_rdata(pt_rdata),
    .pt_ack(pt_ack),
    .pt_done_toggle(pt_done_toggle)
);
wire mismatch =
    (ref_s_axi_awready !== dut_s_axi_awready) ||
    (ref_s_axi_wready !== dut_s_axi_wready) ||
    (ref_s_axi_bvalid !== dut_s_axi_bvalid) ||
    (ref_s_axi_bresp !== dut_s_axi_bresp) ||
    (ref_s_axi_arready !== dut_s_axi_arready) ||
    (ref_s_axi_rvalid !== dut_s_axi_rvalid) ||
    (ref_s_axi_rdata !== dut_s_axi_rdata) ||
    (ref_s_axi_rresp !== dut_s_axi_rresp) ||
    (ref_cam_addr_1 !== dut_cam_addr_1) ||
    (ref_cam_addr_2 !== dut_cam_addr_2) ||
    (ref_xdma_ack !== dut_xdma_ack) ||
    (ref_cam_en !== dut_cam_en) ||
    (ref_dly_step !== dut_dly_step) ||
    (ref_pt_req_toggle !== dut_pt_req_toggle) ||
    (ref_pt_addr !== dut_pt_addr) ||
    (ref_pt_wdata !== dut_pt_wdata) ||
    (ref_pt_rw !== dut_pt_rw);
wire [46+3*AXI_ADDR_WIDTH-1:0] ref_outputs = {ref_s_axi_awready,ref_s_axi_wready,ref_s_axi_bvalid,ref_s_axi_bresp,ref_s_axi_arready,ref_s_axi_rvalid,ref_s_axi_rdata,ref_s_axi_rresp,ref_cam_addr_1,ref_cam_addr_2,ref_xdma_ack,ref_cam_en,ref_dly_step,ref_pt_req_toggle,ref_pt_addr,ref_pt_wdata,ref_pt_rw};
wire [$bits(ref_outputs)-1:0] dut_outputs = {dut_s_axi_awready,dut_s_axi_wready,dut_s_axi_bvalid,dut_s_axi_bresp,dut_s_axi_arready,dut_s_axi_rvalid,dut_s_axi_rdata,dut_s_axi_rresp,dut_cam_addr_1,dut_cam_addr_2,dut_xdma_ack,dut_cam_en,dut_dly_step,dut_pt_req_toggle,dut_pt_addr,dut_pt_wdata,dut_pt_rw};
integer cycles=0, reads=0, writes=0, stalls=0, resets=0, simult=0;
integer i,j,k, seed;
reg [31:0] rnd;
reg [31:0] offsets[0:21];
reg [AXI_ADDR_WIDTH-1:0] hold_data;
reg holding=0;
reg expect_default=0;
reg [31:0] edge_fault;
reg [AXI_ADDR_WIDTH-1:0] before_write;
integer trace;
task tick;
begin
    @(posedge clk); #1;
    cycles=cycles+1;
    if (mismatch) begin
        $display("FAIL id=%0d cycle=%0d ar=%h ref=%h dut=%h",ID,cycles,s_axi_araddr,ref_s_axi_rdata,dut_s_axi_rdata);
        $fatal(1,"cycle comparison");
    end
    $fdisplay(trace,"%0d,%0d,%h,%h,%h,%h,%h,%h,%h,%h,%h", ID,cycles,s_axi_araddr,
        {ref_s_axi_arready,ref_s_axi_rvalid,ref_s_axi_awready,ref_s_axi_wready,ref_s_axi_bvalid},
        {dut_s_axi_arready,dut_s_axi_rvalid,dut_s_axi_awready,dut_s_axi_wready,dut_s_axi_bvalid},
        ref_s_axi_rdata,dut_s_axi_rdata,ref_cam_addr_1,dut_cam_addr_1,ref_outputs,dut_outputs);
    if (holding && !rst && ref_s_axi_rdata !== hold_data) $fatal(1,"R backpressure changed data");
    holding=ref_s_axi_rvalid && !s_axi_rready && !rst;
    hold_data=ref_s_axi_rdata;
    @(negedge clk);
end
endtask
task scramble;
begin
    dbg_cdc_input=$random(seed);
    dbg_cdc_output=$random(seed);
    dbg_cdc_drop=$random(seed);
    dbg_cdc_seq=$random(seed);
    dbg_fault_snapshot=$random(seed);
    dbg_reject_counts=$random(seed);
    dbg_input_pixels=$random(seed);
    dbg_vsync_widths=$random(seed);
    dbg_cam_words=$random(seed);
    dbg_vsyncs=$random(seed);
    dbg_hsyncs=$random(seed);
    dbg_href_raw=$random(seed);
    dbg_vsync_raw=$random(seed);
    dbg_beat_cnt=$random(seed);
    dbg_beat_last=$random(seed);
    dbg_cmd_cnt=$random(seed);
    dbg_axi_sticky=$random(seed);
    dbg_axi_stat=$random(seed);
    dbg_b_cnt=$random(seed);
    dbg_aw_cnt=$random(seed);
    dbg_w_cnt=$random(seed);
    dbg_axi_cnt=$random(seed);
    dbg_zdin=$random(seed);
    dbg_zout=$random(seed);
    dbg_axi_num=$random(seed);
    dbg_state=$random(seed);
    dbg_last_cnt=$random(seed);
    dbg_wd_cnt=$random(seed);
    dbg_xdma_req=$random(seed);
    dbg_i2c_status=$random(seed);
    dbg_pclk_cnt=$random(seed);
    dbg_sys_status=$random(seed);
    dbg_clk_status=$random(seed);
    pt_rdata=$random(seed); pt_ack=$random(seed);
end
endtask
task read_at(input [AXI_ADDR_WIDTH-1:0] address, input integer stall_n, input integer do_write);
begin
    s_axi_araddr=address; s_axi_arvalid=1; s_axi_rready=0;
    s_axi_awaddr=address; s_axi_awvalid=do_write; s_axi_wvalid=do_write;
    s_axi_wdata=$random(seed); s_axi_wstrb=$random(seed);
    scramble;
    reads=reads+1;
    if(do_write) begin writes=writes+1; simult=simult+1; end
    tick; // AR edge
    s_axi_arvalid=0; s_axi_awvalid=0; s_axi_wvalid=0;
    scramble; // must use this edge's values, not values at AR
    edge_fault=dbg_fault_snapshot;
    pt_done_toggle=~pt_done_toggle;
    tick; // data edge
    if(!ref_s_axi_rvalid) $fatal(1,"missing response on fixed edge");
    if(expect_default && ID!=5 && ref_s_axi_rdata !== {AXI_ADDR_WIDTH{1'b1}}) $fatal(1,"illegal/alias default");
    if((address === BASE_ADDR) && ref_s_axi_rdata !== AXI_ADDR_WIDTH'(edge_fault)) $fatal(1,"data edge or first-case priority");
    for(k=0;k<stall_n;k=k+1) begin
        s_axi_arvalid=1; s_axi_araddr=$random(seed); scramble; stalls=stalls+1; tick;
    end
    s_axi_arvalid=0; s_axi_rready=1; tick;
    s_axi_rready=0; tick;
end
endtask
initial begin
    seed=32'h453123+ID*237;
    trace=$fopen($sformatf("trace_%0d.csv",ID),"w");
    if(!trace) $fatal(1,"trace open");
    $fdisplay(trace,"pair,cycle,araddr,ref_axi,dut_axi,ref_rdata,dut_rdata,ref_cam1,dut_cam1,ref_all_outputs,dut_all_outputs");
    offsets[0]='h00; offsets[1]='h40; offsets[2]='h80; offsets[3]='hc0;
    offsets[4]='h190; offsets[5]='h1a0; offsets[6]='h1b0; offsets[7]='h1c0;
    offsets[8]='h30; offsets[9]='h20; offsets[10]='h50; offsets[11]='h90;
    offsets[12]='ha0; offsets[13]='hf0; offsets[14]='hb0; offsets[15]='he0;
    offsets[16]='h60; offsets[17]='h10; offsets[18]='h70; offsets[19]='hd0;
    offsets[20]='h110; offsets[21]='h120;
    rst=1; resets=resets+1; tick; tick; rst=0;
    // All implemented addresses, simultaneous writes and every low-bit alias.
    for(i=0;i<22;i=i+1) begin
        read_at(BASE_ADDR+offsets[i], 5, 1);
        expect_default=1;
        for(j=1;j<16;j=j+1) read_at(BASE_ADDR+offsets[i]+j, 0, 0);
        read_at((BASE_ADDR+offsets[i]) ^ (64'h1 << (AXI_ADDR_WIDTH-1)), 2, 0);
        expect_default=0;
    end
    expect_default=1;
    read_at(BASE_ADDR+'h100,8,1); // write-only command, invalid read
    read_at(BASE_ADDR+'h180,1,0);
    expect_default=0;
    // Collision parameter: all constant expressions evaluate X. First case wins.
    if(ID==5) begin
        read_at({AXI_ADDR_WIDTH{1'bx}},4,0);
    end
    if(ID!=5) begin
        reads=reads+2; writes=writes+2; simult=simult+1;
        // Write on AR edge: read sees the newly stored value on next edge.
        s_axi_arvalid=1; s_axi_araddr=BASE_ADDR+'h80; s_axi_rready=0;
        s_axi_awvalid=1; s_axi_wvalid=1; s_axi_awaddr=BASE_ADDR+'h80; s_axi_wdata='h13579bdf;
        tick; s_axi_arvalid=0; s_axi_awvalid=0; s_axi_wvalid=0;
        tick;
        if(ref_s_axi_rdata !== AXI_ADDR_WIDTH'('h13579bdf)) $fatal(1,"AR edge write/read");
        s_axi_rready=1; tick; s_axi_rready=0; tick;
        // Write on data edge: read sees pre-NBA register, write commits separately.
        before_write=ref_cam_addr_1;
        s_axi_arvalid=1; s_axi_araddr=BASE_ADDR+'h80; tick; s_axi_arvalid=0;
        s_axi_awvalid=1; s_axi_wvalid=1; s_axi_awaddr=BASE_ADDR+'h80; s_axi_wdata='h2468ace0;
        tick;
        if(ref_s_axi_rdata !== before_write || ref_cam_addr_1 !== AXI_ADDR_WIDTH'('h2468ace0)) $fatal(1,"data edge read/write priority");
        s_axi_awvalid=0; s_axi_wvalid=0; s_axi_rready=1; tick; s_axi_rready=0; tick;
    end
    // Reset on AR edge, data edge and held R response, with writes asserted.
    for(i=0;i<3;i=i+1) begin
        s_axi_arvalid=1; s_axi_araddr=BASE_ADDR+'h80;
        s_axi_awvalid=1; s_axi_wvalid=1; s_axi_awaddr=BASE_ADDR+'h80;
        s_axi_wdata='hdeadbeef; s_axi_rready=0;
        if(i==0) rst=1;
        tick;
        s_axi_arvalid=0;
        if(i==1) rst=1;
        tick;
        rst=1; resets=resets+1; tick;
        if(ref_cam_addr_1 !== AXI_ADDR_WIDTH'(32'h12345678) || ref_s_axi_rvalid || ref_s_axi_bvalid || ref_s_axi_rdata !== 0) $fatal(1,"reset beats read/write");
        s_axi_awvalid=0; s_axi_wvalid=0; rst=0; tick;
    end
    // Independent random streams, including protocol-unfriendly mixed VALID.
    for(i=0;i<20000;i=i+1) begin
        rnd=$random(seed);
        rst=(rnd[9:0]==0); if(rst) resets=resets+1;
        s_axi_arvalid=rnd[0]; s_axi_rready=rnd[1];
        s_axi_awvalid=rnd[2]; s_axi_wvalid=rnd[3]; s_axi_bready=rnd[4];
        s_axi_araddr=BASE_ADDR+offsets[(rnd>>16)%22]+(rnd[5] ? 0 : rnd[15:12]);
        if(rnd[6]) s_axi_araddr=s_axi_araddr ^ (64'h1 << (AXI_ADDR_WIDTH-1));
        s_axi_awaddr=BASE_ADDR+offsets[(rnd>>8)%22];
        s_axi_wdata=$random(seed); s_axi_wstrb=$random(seed);
        scramble;
        if(rnd[7]) pt_done_toggle=~pt_done_toggle;
        if(s_axi_arvalid && ref_s_axi_arready) reads=reads+1;
        if(s_axi_awvalid && s_axi_wvalid) writes=writes+1;
        if(s_axi_arvalid && ref_s_axi_arready && s_axi_awvalid && s_axi_wvalid) simult=simult+1;
        if(ref_s_axi_rvalid && !s_axi_rready) stalls=stalls+1;
        tick;
    end
    rst=1; tick; $fclose(trace);
    $display("PASS pair=%0d width=%0d cycles=%0d reads=%0d writes=%0d stalls=%0d resets=%0d simultaneous=%0d",ID,AXI_ADDR_WIDTH,cycles,reads,writes,stalls,resets,simult);
    done=1;
end
endmodule
module tb_camera_read_decode;
wire [5:0] done;
camera_pair #(.ID(0)) p0(done[0]);
camera_pair #(.ID(1),.BASE_ADDR(32'h20000100)) p1(done[1]);
camera_pair #(.ID(2),.BASE_ADDR(32'hffffff80)) p2(done[2]);
camera_pair #(.ID(3),.AXI_ADDR_WIDTH(64),.BASE_ADDR(64'h120000000)) p3(done[3]);
camera_pair #(.ID(4),.AXI_ADDR_WIDTH(16),.BASE_ADDR(32'h00000000)) p4(done[4]);
camera_pair #(.ID(5),.BASE_ADDR(32'hxxxxxxxx)) p5(done[5]);
initial begin wait(&done); $display("PASS ALL 6 actual-module cycle miters"); $finish; end
initial begin #2000000; $fatal(1,"timeout"); end
endmodule
