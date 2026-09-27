"""Byte-preserving diagnostic-only RTL edit, with mandatory .bak snapshots."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def edit(name, pairs):
    p=ROOT/name
    old=p.read_bytes(); new=old
    if p.with_name(p.name+'.rejection_diag.bak').exists():
        assert b'dbg_fault_snapshot' in old
        return
    for a,b in pairs:
        a=a.encode('ascii'); b=b.encode('ascii')
        assert new.count(a)==1,(name,a,new.count(a))
        new=new.replace(a,b)
    bak=p.with_name(p.name+'.rejection_diag.bak')
    assert not bak.exists(),bak
    bak.write_bytes(old);p.write_bytes(new)

edit('source/ov5640/ov5640_ddr/ov5640_ddr.v',[
('    output [31:0]    dbg_axi_cnt', '''    output reg [31:0] dbg_fault_snapshot,
    output [31:0] dbg_reject_counts,
    output reg [31:0] dbg_input_pixels,
    output [31:0]    dbg_axi_cnt'''),
('assign dma_abort_req = capture_bad;', '''assign dma_abort_req = capture_bad;
// Read-only evidence, retained across local flush. First source fault wins.
// Snapshot [31]=overflow, [30]=short, [29]=DMA abort without source fault,
// [28]=tag phase, [27:0]=accepted pixel count at that event.
reg [15:0] diag_overflows, diag_shorts;
reg [31:0] diag_input_count;
wire diag_short = raw_sof && !capture_complete;
wire diag_fault = capture_open && !capture_flush && !capture_bad &&
                  !m_vsync && (capture_overflow || diag_short);
assign dbg_reject_counts = {diag_overflows, diag_shorts};
always @(posedge axi_clk) begin
    if(axi_rst) begin
        dbg_fault_snapshot <= 0;
        diag_overflows <= 0;
        diag_shorts <= 0;
        diag_input_count <= 0;
        dbg_input_pixels <= 0;
    end else begin
        // Count every offered pixel, independently of admission/quota/flush.
        if(raw_sof) begin
            dbg_input_pixels <= diag_input_count;
            diag_input_count <= s_data_valid ? 1 : 0;
        end else if(s_data_valid) diag_input_count <= diag_input_count + 1'b1;
        if(diag_fault) begin
            dbg_fault_snapshot <= {capture_overflow, diag_short, 1'b0,
                                   !frame_active, pixel_count[27:0]};
            if(capture_overflow) diag_overflows <= diag_overflows + 1'b1;
            if(diag_short) diag_shorts <= diag_shorts + 1'b1;
        end else if(dma_abort && !capture_bad) begin
            dbg_fault_snapshot <= {2'b00, 1'b1, !frame_active, pixel_count[27:0]};
        end
    end
end''')])
edit('source/ov5640/ov5640_top.v',[
('    ov5640_ddr #(', '''    wire [31:0] diag_fault_snapshot, diag_reject_counts, diag_input_pixels;
    ov5640_ddr #('''),
('        .dma_abort      (cam_dma_abort),', '''        .dbg_fault_snapshot(diag_fault_snapshot),
        .dbg_reject_counts(diag_reject_counts),
        .dbg_input_pixels(diag_input_pixels),
        .dma_abort      (cam_dma_abort),'''),
('    // [DBG] camera activity counters', '''    // VSYNC high widths in video_clk cycles (pre-FIR), saturating at 65535.
    // Minimum ignores reset's initial partial pulse; first complete pulse seeds it.
    reg diag_vs_q;
    reg [15:0] diag_vs_width, diag_vs_last, diag_vs_min;
    always @(posedge video_clk) begin
        if(video_rst) begin
            diag_vs_q <= 0;
            diag_vs_width <= 0;
            diag_vs_last <= 0;
            diag_vs_min <= 16'hffff;
        end else begin
            diag_vs_q <= video_vsync;
            if(video_vsync) begin
                if(!diag_vs_q) diag_vs_width <= 1;
                else if(diag_vs_width != 16'hffff) diag_vs_width <= diag_vs_width + 1'b1;
            end else if(diag_vs_q) begin
                diag_vs_last <= diag_vs_width;
                if(diag_vs_width < diag_vs_min) diag_vs_min <= diag_vs_width;
            end
        end
    end
    // [DBG] camera activity counters'''),
('        .dbg_cam_words         (dbg_cam_words),', '''        .dbg_fault_snapshot    (diag_fault_snapshot),
        .dbg_reject_counts     (diag_reject_counts),
        .dbg_input_pixels      (diag_input_pixels),
        .dbg_vsync_widths      ({diag_vs_min, diag_vs_last}),
        .dbg_cam_words         (dbg_cam_words),''')])
edit('source/ov5640/ov5640_reg.v',[
('    input  [31:0]                     dbg_cam_words', '''    input [31:0] dbg_fault_snapshot,
    input [31:0] dbg_reject_counts,
    input [31:0] dbg_input_pixels,
    input [31:0] dbg_vsync_widths,
    input  [31:0]                     dbg_cam_words'''),
('REG_ACK:        rdata <= {{AXI_ADDR_WIDTH-2{1\'b0}}, xdma_ack};','REG_ACK:        rdata <= dbg_fault_snapshot; // read-only; ACK writes unchanged'),
('REG_DBG_CAM_WORDS: rdata <= dbg_cam_words;','REG_DBG_CAM_WORDS: rdata <= dbg_input_pixels;'),
('REG_DBG_ZDIN:      rdata <= dbg_i2c_status;','REG_DBG_ZDIN:      rdata <= dbg_vsync_widths;'),
('REG_DBG_BEAT_CNT:  rdata <= dbg_beat_cnt;','REG_DBG_BEAT_CNT:  rdata <= dbg_reject_counts;')])
print('Diagnostic-only RTL changes applied; source backups end in .rejection_diag.bak')
