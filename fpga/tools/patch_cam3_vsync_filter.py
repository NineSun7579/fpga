"""Byte-only source edit; preserve existing encoding/newlines and save backups."""
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
tag = datetime.now().strftime('%Y%m%d_%H%M%S')

def edit(name, replacements):
    p = ROOT / name
    original = p.read_bytes()
    data = original
    if b'VSYNC_STABLE_CYCLES' in original:
        print(name, 'already patched; skipped')
        return
    nl = b'\r\n' if b'\r\n' in original else b'\n'
    for old, new in replacements:
        old = old.encode('ascii').replace(b'\n', nl)
        new = new.encode('ascii').replace(b'\n', nl)
        assert data.count(old) == 1, (name, old, data.count(old))
        data = data.replace(old, new, 1)
    backup = p.with_name(p.name + '.bak_cam3_vsync_' + tag)
    with backup.open('xb') as f:
        f.write(original)
    p.write_bytes(data)
    print(name, 'backup:', backup.name)

FILTER = '''// VSYNC_FILTER_BEGIN
// 0: combinational bypass. N>0: accept only N consecutive opposite samples.
// Both edges are delayed by N PCLK samples (64/84 MHz = 0.762 us).
// Raw diagnostics above intentionally remain upstream. HREF/data are untouched.
// Requires real VSYNC pulses and edge-to-active-video blanking to exceed N
// samples plus the existing capture latency. No timeout or synthetic frames.
wire capture_vsync;
generate
    if (VSYNC_STABLE_CYCLES == 0) begin : g_vsync_bypass
        assign capture_vsync = cam_vsync;
    end else begin : g_vsync_filter
        localparam COUNT_W = (VSYNC_STABLE_CYCLES <= 1) ? 1 :
                             $clog2(VSYNC_STABLE_CYCLES);
        reg [COUNT_W-1:0] stable_count;
        reg stable_vsync;
        assign capture_vsync = stable_vsync;
        always @(posedge cam_pclk or negedge ov_rst_n) begin
            if (!ov_rst_n) begin
                stable_count <= {COUNT_W{1'b0}};
                stable_vsync <= 1'b0;
            end else if (cam_vsync == stable_vsync) begin
                stable_count <= {COUNT_W{1'b0}};
            end else if (stable_count == VSYNC_STABLE_CYCLES - 1) begin
                stable_count <= {COUNT_W{1'b0}};
                stable_vsync <= cam_vsync;
            end else begin
                stable_count <= stable_count + 1'b1;
            end
        end
    end
endgenerate
// VSYNC_FILTER_END

'''

edit('source/ov5640/ov5640/ov5640.v', [
    ('    parameter DEVICE = "PG"', '    parameter integer VSYNC_STABLE_CYCLES = 0,\n    parameter DEVICE = "PG"'),
    ('cmos_capture #(\n', FILTER + 'cmos_capture #(\n'),
    ('.cam_vsync  (cam_vsync)', '.cam_vsync  (capture_vsync)'),
])
edit('source/ov5640/ov5640_top.v', [
    ('    parameter [7:0] IODELAY_STEP = 8\'d40,', '    parameter [7:0] IODELAY_STEP = 8\'d40,\n    parameter integer VSYNC_STABLE_CYCLES = 0,'),
    ('        .SLAVE_ADDR(SLAVE_ADDR)', '        .VSYNC_STABLE_CYCLES(VSYNC_STABLE_CYCLES),\n        .SLAVE_ADDR(SLAVE_ADDR)'),
])
edit('source/top.v', [
    ("    .BASE_ADDR       (32'h2000_0400),", "    .BASE_ADDR       (32'h2000_0400),\n    .VSYNC_STABLE_CYCLES(64), // cam3 only: 0.762 us at 84 MHz"),
    ('//      no FIR / median / Kalman -- module defaults keep all filters bypassed) ----', '//      VSYNC qualified for 64 PCLK; pixel-path settings unchanged) ----'),
])
