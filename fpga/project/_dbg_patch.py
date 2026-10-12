import shutil

# ---------------- ov5640_reg.v ----------------
P = 'source/ov5640/ov5640_reg.v'
shutil.copyfile(P, P + '.bak_dbg')
raw = open(P, 'rb').read()

# ports: replace from 'cam_en' through '\n);'
i = raw.find(b'cam_en                \n);')
assert i != -1, 'reg port anchor missing'
j = i + len(b'cam_en                ')
raw = raw[:j] + (b"        ,\n"
                 b"    input  [31:0]                     dbg_cam_words         ,\n"
                 b"    input  [31:0]                     dbg_vsyncs") + raw[j:]

old_lp = b"localparam REG_CAM_ADDR_2= BASE_ADDR + 32'hc0;"
assert old_lp in raw, 'reg localparam anchor missing'
raw = raw.replace(old_lp, old_lp + b"\n"
                  b"localparam REG_DBG_CAM_WORDS = BASE_ADDR + 32'h30;\n"
                  b"localparam REG_DBG_VSYNCS    = BASE_ADDR + 32'h34;")

old_def = b"                    default:        rdata <="
assert old_def in raw, 'reg default anchor missing'
raw = raw.replace(old_def,
                  b"                    REG_DBG_CAM_WORDS: rdata <= dbg_cam_words;\n"
                  b"                    REG_DBG_VSYNCS:    rdata <= dbg_vsyncs;\n"
                  + old_def, 1)
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_top.v ----------------
P = 'source/ov5640/ov5640_top.v'
shutil.copyfile(P, P + '.bak_dbg')
lines = open(P, 'rb').read().split(b'\n')

hit = None
for i, l in enumerate(lines):
    if l.strip().startswith(b'.cam_addr_2') and b'(cam_addr_2' in l:
        hit = i
        break
assert hit is not None, 'cam_addr_2 connection not found'
stripped = lines[hit].rstrip()
assert stripped.endswith(b')'), repr(stripped[-20:])
indent = lines[hit][:len(lines[hit]) - len(lines[hit].lstrip())]
lines[hit] = stripped[:-1] + b'),'
lines.insert(hit + 1, indent + b'.dbg_cam_words         (dbg_cam_words),')
lines.insert(hit + 2, indent + b'.dbg_vsyncs            (dbg_vsyncs   )')

inst = None
for i, l in enumerate(lines):
    if l.strip().startswith(b'ov5640_reg #('):
        inst = i
        break
assert inst is not None, 'ov5640_reg instantiation not found'
CNT = [
    b'',
    b'    // [DBG] camera activity counters (read via ov5640_reg +0x30/+0x34)',
    b'    reg [31:0] dbg_cam_words;',
    b'    always @(posedge video_clk) begin',
    b"        if (video_rst) dbg_cam_words <= 32'd0;",
    b"        else if (cam_s_data_valid) dbg_cam_words <= dbg_cam_words + 32'd1;",
    b'    end',
    b'    reg [31:0] dbg_vsyncs;',
    b'    reg [2:0]  dbg_vs_ff;',
    b'    always @(posedge video_clk) dbg_vs_ff <= {dbg_vs_ff[1:0], video_vsync};',
    b'    always @(posedge video_clk) begin',
    b"        if (video_rst) dbg_vsyncs <= 32'd0;",
    b"        else if (dbg_vs_ff[2:1] == 2'b01) dbg_vsyncs <= dbg_vsyncs + 32'd1;",
    b'    end',
    b'',
]
lines = lines[:inst] + CNT + lines[inst:]
open(P, 'wb').write(b'\n'.join(lines))
print('patched', P, 'lines', len(lines))
