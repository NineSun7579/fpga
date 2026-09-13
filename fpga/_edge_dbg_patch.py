import shutil

# ============================================================================
# [EDGE-DBG 2026-09-13] 边缘通路可观测性: 4 个只读计数器
#   +0x180 dbg_pp_beats  : cam_prep_link 的 pp_valid 拍数 (tap 是否在出像素)
#   +0x184 dbg_prep_aw   : prep2 axi_dma_write 的 AW 握手次数 (写命令是否被 DDR 受理)
#   +0x188 dbg_prep_w    : prep2 的 W beat 握手次数 (数据是否真的推进)
#   +0x18C dbg_prep_b    : prep2 的 B 响应次数 (事务是否收尾)
# 用一次编译定位链路断点。
# ============================================================================

# ---------------- A) prep_regs.v ----------------
P = 'source/preprocess/prep_regs.v'
shutil.copyfile(P, P + '.bak_dbg4')
raw = open(P, 'rb').read()

# A1) 端口: 在 ts_value3 前加 4 个 dbg 输入
a = b'    output wire [31:0]                   ts_value3\n);'
assert raw.count(a) == 1, 'A1'
raw = raw.replace(a, b'    output wire [31:0]                   ts_value3,\n'
                     b'    // ---- [EDGE-DBG] read-only debug counters ----\n'
                     b'    input  wire [31:0]                   dbg_pp_beats,\n'
                     b'    input  wire [31:0]                   dbg_prep_aw,\n'
                     b'    input  wire [31:0]                   dbg_prep_w,\n'
                     b'    input  wire [31:0]                   dbg_prep_b\n);')

# A2) 读多路器: 0x70 那行的块之后追加 0x80..0x8C? 用注释里的自由区间
a = b"            8'h70: rdata_mux = r_ts0;"
assert raw.count(a) == 1, 'A2'
raw = raw.replace(a, a + b"\n"
                     b"            // [EDGE-DBG] link observability counters\n"
                     b"            8'h80: rdata_mux = dbg_pp_beats;\n"
                     b"            8'h84: rdata_mux = dbg_prep_aw;\n"
                     b"            8'h88: rdata_mux = dbg_prep_w;\n"
                     b"            8'h8C: rdata_mux = dbg_prep_b;")

open(P, 'wb').write(raw)
print('A) prep_regs.v: 4 dbg ports + read mux 0x80..0x8C')

# ---------------- B) top.v ----------------
P = 'source/top.v'
shutil.copyfile(P, P + '.bak_dbg4')
raw = open(P, 'rb').read()

# B1) 在 prep_frame_cnt 之前插入 4 个计数器 + 连续赋值
a = b'reg [7:0] prep_frame_cnt;'
assert raw.count(a) == 1, 'B1'
raw = raw.replace(a,
    b'// [EDGE-DBG] link observability counters (read via prep_regs +0x180..0x18C)\n'
    b'reg [31:0] dbg_pp_beats, dbg_prep_aw, dbg_prep_w, dbg_prep_b;\n'
    b'always @(posedge axi_clk) begin\n'
    b'    if (axi_rst) begin\n'
    b'        dbg_pp_beats <= 32\'d0; dbg_prep_aw <= 32\'d0;\n'
    b'        dbg_prep_w  <= 32\'d0; dbg_prep_b  <= 32\'d0;\n'
    b'    end\n'
    b'    else begin\n'
    b'        if (prep_pp_valid)                          dbg_pp_beats <= dbg_pp_beats + 32\'d1;\n'
    b'        if (prep2_axi_awvalid && prep2_axi_awready) dbg_prep_aw  <= dbg_prep_aw  + 32\'d1;\n'
    b'        if (prep2_axi_wvalid  && prep2_axi_wready)  dbg_prep_w   <= dbg_prep_w   + 32\'d1;\n'
    b'        if (prep2_axi_bvalid  && prep2_axi_bready)  dbg_prep_b   <= dbg_prep_b   + 32\'d1;\n'
    b'    end\n'
    b'end\n'
    b'reg [7:0] prep_frame_cnt;')

# B2) prep_regs 例化接线: 在 ts_value3 之后加 4 个连接
a = b'    .ts_value3        ()'
assert raw.count(a) == 1, 'B2 anchor: %d' % raw.count(a)
raw = raw.replace(a, b'    .ts_value3       (),\n'
                     b'    .dbg_pp_beats    (dbg_pp_beats ),\n'
                     b'    .dbg_prep_aw     (dbg_prep_aw  ),\n'
                     b'    .dbg_prep_w      (dbg_prep_w   ),\n'
                     b'    .dbg_prep_b      (dbg_prep_b   )')

open(P, 'wb').write(raw)
print('B) top.v: 4 counters + prep_regs connections')

for p in ('source/preprocess/prep_regs.v', 'source/top.v'):
    fin = open(p, 'rb').read()
    print('  %-38s dbg refs=%d' % (p, fin.count(b'dbg_prep') + fin.count(b'dbg_pp_beats')))
