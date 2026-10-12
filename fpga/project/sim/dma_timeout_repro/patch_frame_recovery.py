from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
def edit(name, fn):
    p = ROOT / name
    src = p.read_bytes()
    dst = fn(src)
    assert dst != src, name
    bak = p.with_name(p.name + '.frame_recovery.bak')
    assert not bak.exists(), str(bak)
    shutil.copyfile(p, bak)
    p.write_bytes(dst)

def rep(s, a, b):
    a, b = a.encode('ascii'), b.encode('ascii')
    assert a in s, a
    return s.replace(a, b)

def dma(s):
    s=rep(s,'parameter \t\tBURST_LEN','parameter WD_LIMIT = 24\'hFFFFFF,\n\t\tparameter \t\tBURST_LEN')
    s=rep(s,'//trans data in','input abort_req, // sticky source fault, held until retirement\n    output reg data_in_abort, // failed command, all AXI obligations retired\n\n\t//trans data in')
    s=rep(s,"(abort_r == 1'b0))begin", "(abort_r == 1'b0) && !abort_req)begin")
    s=rep(s,"(wd_cnt == 24'hFFFFFF)","(wd_cnt == WD_LIMIT)")
    s=rep(s,"else if(!abort_r && burst_trans", "else if(trans && abort_req)\n        abort_r <= 1'b1;\n    else if(!abort_r && burst_trans")
    s=rep(s,'assign abort_done = abort_r && m_axi_bvalid && m_axi_bready;', '''wire b_fire = m_axi_bvalid && m_axi_bready;
wire failed = abort_r || abort_req || (b_fire && m_axi_bresp[1]);
assign abort_done = trans && failed &&
                    (b_fire || (abort_r && !burst_trans && !m_axi_awvalid));''')
    s=rep(s,"t_m_axi_wstrb   = abort_r ? {KEEP_WIDTH{1'b1}}", "t_m_axi_wstrb   = abort_r ? {KEEP_WIDTH{1'b0}}")
    start=s.index(b'// One completion per command')
    s=s[:start]+b'''// Success and failure are mutually exclusive and follow real external B.
always @(posedge clk) begin
    if(rst) begin
        data_in_last <= 1'b0;
        data_in_abort <= 1'b0;
    end else begin
        data_in_last <= trans && b_fire && (len == 0) && !failed;
        data_in_abort <= abort_done;
    end
end

endmodule
'''
    return s

def ctrl(s):
    s=rep(s,'input          dma_done', 'input          dma_abort,\n    input          frame_good,\n    input          dma_done')
    s=rep(s,'wire frame_done = dma_done && (curr_state == DATA);', '''wire frame_done = dma_done && frame_good && (curr_state == DATA);
    wire frame_failed = (dma_abort || (dma_done && !frame_good)) && (curr_state == DATA);
    wire publish = dma_done && (curr_state == WAIT_TAG_DONE);''')
    s=rep(s,'if(frame_done)begin\n                    next_state', 'if(frame_failed) next_state = IDLE;\n                else if(frame_done)begin\n                    next_state')
    s=rep(s,'if(tag_fire)begin', 'if(dma_abort) next_state = IDLE;\n                else if(tag_fire)begin')
    s=rep(s,'if(dma_done) next_state = IDLE;', 'if(dma_done || dma_abort) next_state = IDLE;')
    s=rep(s,'if(frame_done)begin\n                w_ping', 'if(publish)begin\n                w_ping')
    s=rep(s,'else if(axi_vsync_rise)begin', 'else if(axi_vsync_rise && (curr_state == IDLE))begin')
    s=rep(s,'else if(frame_done)begin\n            frame_cnt', 'else if(publish)begin\n            frame_cnt')
    s=rep(s,"assign tag_data    = {{(AXI_DATA_WIDTH-32){1'b0}}, frame_cnt};", "assign tag_data    = {{(AXI_DATA_WIDTH-32){1'b0}}, (frame_cnt + 32'd1)};")
    s=rep(s,'if(frame_done)begin\n                if(w_ping)', 'if(publish)begin\n                if(w_ping)')
    s=rep(s,"if(xdma_ack[0]) begin", "if(xdma_ack[0] || ((curr_state == IDLE) && vsync_pending && !w_ping)) begin")
    s=rep(s,"if(xdma_ack[1]) begin", "if(xdma_ack[1] || ((curr_state == IDLE) && vsync_pending && w_ping)) begin")
    s=rep(s,'else if(frame_done) last_cnt', 'else if(publish) last_cnt')
    return s

def pack(s):
    s=rep(s,'input          axi_rst        ,', 'input          axi_rst        ,\n    input          capture_flush,\n    output         capture_overflow,\n    wire_unused_placeholder')
    s=rep(s,'    wire_unused_placeholder','')
    # Local reset is intentionally confined to packer/FIFOs, never DMA/AXI.
    s=rep(s,'    reg             wr_en;', '    wire local_rst = axi_rst | capture_flush;\n    wire out_full;\n    assign capture_overflow = (wr_en && full) || (fifo_we && out_full);\n    reg             wr_en;')
    s=s.replace(b'if(axi_rst)',b'if(local_rst)').replace(b'if (axi_rst)',b'if (local_rst)').replace(b'.rst(axi_rst)',b'.rst(local_rst)')
    s=rep(s,'assign axi_data_valid = !empty;', 'assign axi_data_valid = !empty && !local_rst;')
    s=rep(s,'.full(),', '.full(out_full),')
    s=rep(s,'wire rd_en_drm = !(empty_drm | almost_full_out);', 'wire rd_en_drm = !(empty_drm | almost_full_out | local_rst);')
    # clear data-bearing packer registers as well as their validity
    s=rep(s,'if(s_data_valid)begin', "if(local_rst)begin\n                cam_data_temp <= 0;\n            end\n            else if(s_data_valid)begin") if False else s
    # cam_data_temp/din need not reset for correctness: cnt=0 repopulates each byte
    return s

def en(s):
    s=rep(s,'input          axi_rst      ,', 'input          axi_rst      ,\n    input          capture_stop,')
    s=rep(s,'if(axi_rst)begin\n        curr_state', 'if(axi_rst || capture_stop)begin\n        curr_state')
    s=rep(s,'!engine_busy)', '!engine_busy && !capture_stop)')
    s=rep(s,'(curr_state == DATA);','(curr_state == DATA) && !capture_stop && !s_vsync;')
    s=rep(s,'!engine_busy;', '!engine_busy && !capture_stop;')
    s=rep(s,'assign m_data       = s_data;', 'assign m_hsync = s_hsync;\nassign m_data       = s_data;')
    return s

def wrapper(s):
    s=rep(s,'input          dma_done', 'input          dma_abort,\n    output         dma_abort_req,\n    input          dma_done')
    marker=b'ov5640_ddr_w_en #('
    insert=b'''// Capture validity belongs to the admitted SOF, never to a DMA timeout.
// Flush only on DMA retirement (all external W/B obligations are finished).
reg [2:0] flush_count;
wire capture_flush = (flush_count != 0);
reg capture_open, capture_bad;
reg [31:0] pixel_count, pixel_limit;
reg raw_vsync_q;
wire raw_sof = s_vsync && !raw_vsync_q;
wire capture_overflow;
wire capture_complete = capture_open && (pixel_count == pixel_limit);
wire frame_good = capture_complete && !capture_bad && !capture_overflow;
wire capture_stop = capture_flush || capture_bad || capture_complete;
assign dma_abort_req = capture_bad;
always @(posedge axi_clk) begin
    if(axi_rst) begin
        flush_count <= 4;
        raw_vsync_q <= 0;
    end else begin
        raw_vsync_q <= s_vsync;
        if(dma_done || dma_abort) flush_count <= 4;
        else if(capture_flush) flush_count <= flush_count - 1'b1;
    end
end
always @(posedge axi_clk) begin
    if(axi_rst || capture_flush) begin
        capture_open <= 0;
        capture_bad <= 0;
        pixel_count <= 0;
        pixel_limit <= 0;
    end else if(m_vsync) begin
        capture_open <= 1;
        capture_bad <= (cam_data_len == 0);
        pixel_count <= 0;
        pixel_limit <= (cam_data_len * AXI_DATA_WIDTH) / DATA_WIDTH;
    end else if(capture_open) begin
        if(m_data_valid) pixel_count <= pixel_count + 1'b1;
        if(capture_overflow || (raw_sof && !capture_complete)) capture_bad <= 1;
    end
end

'''
    s=s.replace(marker,insert+marker,1)
    s=rep(s,'.engine_busy   (engine_busy   )', '.capture_stop  (capture_stop),\n    .engine_busy   (engine_busy | capture_flush)')
    # insert new packer ports at unique data_len location
    s=rep(s,'.data_len       (cam_data_len   )', '.capture_flush (capture_flush),\n    .capture_overflow(capture_overflow),\n    .data_len       (cam_data_len   )')
    s=rep(s,'.dma_done       (dma_done       )', '.dma_abort      (dma_abort),\n    .frame_good     (frame_good),\n    .dma_done       (dma_done       )')
    return s

def camtop(s):
    s=rep(s,'input                         cam_dma_done', 'input                         cam_dma_abort,\n    output                        cam_dma_abort_req,\n    input                         cam_dma_done')
    return rep(s,'.dma_done       (cam_dma_done)', '.dma_abort      (cam_dma_abort),\n        .dma_abort_req  (cam_dma_abort_req),\n        .dma_done       (cam_dma_done)')

def top(s):
    for cam in ['cam','cam2','cam3']:
        s=rep(s,f'wire {cam}_dma_done;',f'wire {cam}_dma_done;\nwire {cam}_dma_abort, {cam}_dma_abort_req;')
        s=rep(s,f'.cam_dma_done({cam}_dma_done)',f'.cam_dma_abort({cam}_dma_abort),\n    .cam_dma_abort_req({cam}_dma_abort_req),\n    .cam_dma_done({cam}_dma_done)')
        # DMA connection before data input
        name={'cam':'ov5640_axi_dma_write','cam2':'cam2_axi_dma_write','cam3':'cam3_axi_dma_write'}[cam]
        s=rep(s,name+'(',name+f'(\n    .abort_req({cam}_dma_abort_req),\n    .data_in_abort({cam}_dma_abort),')
    s=rep(s,') prep_axi_dma_write(', ") prep_axi_dma_write(\n    .abort_req(1'b0),\n    .data_in_abort(),")
    return s

edit('source/axi_dma/axi_dma_write.v',dma)
edit('source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v',ctrl)
edit('source/ov5640/ov5640_ddr/ov5640_ddr_w.v',pack)
edit('source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v',en)
edit('source/ov5640/ov5640_ddr/ov5640_ddr.v',wrapper)
edit('source/ov5640/ov5640_top.v',camtop)
edit('source/top.v',top)
edit('source/axi_dma/axi_dma.v', lambda s: rep(rep(s,'output                        data_in_last', 'output                        data_in_abort,\n    output                        data_in_last'),') axi_dma_write_inst(', ") axi_dma_write_inst(\n    .abort_req(1'b0),\n    .data_in_abort(data_in_abort),"))
print('Applied frame recovery; original GBK bytes retained, backups *.frame_recovery.bak')
