import shutil

# ============================================================================
# [NPU-RESTORE 2026-09-13] top.v 改造:
#   A) 恢复 NPU 例化区(从 bak_npu_removal 原样搬回, 含 6 个 ifndef 块 + 线网声明)
#   B) 恢复 npu_clk / npu_rst 赋值
#   C) 注释掉 preprocess 例化(cam_prep_link + preprocess_top)
#   D) prep_wr_* 重新绑零(preprocess 不再驱动)
#   保留不变: RAW 直连通路、SID 竞态修复、诊断计数器、时钟旁路等既有修复
# ============================================================================

CUR = 'source/top.v'
BAK = 'source/top.v.bak_npu_removal'
shutil.copyfile(CUR, CUR + '.bak_pre_npu_restore')

cur = open(CUR, 'rb').read()
bak = open(BAK, 'rb').read()

def line_start(raw, idx):
    while idx > 0 and raw[idx-1:idx] not in (b'\n', b'\r'):
        idx -= 1
    return idx

# ---------- A) 替换 NPU 区域 ----------
m1 = b'wire [AXI_ID_LEN-1:0]   npu_reg_axi_awid'
m2 = b'axi_crossbar_7x3 #('
i_cs, i_ce = cur.find(m1), cur.find(m2)
assert i_cs != -1 and i_ce != -1 and i_cs < i_ce, 'cur markers'
i_bs, i_be = bak.find(m1), bak.find(m2)
assert i_bs != -1 and i_be != -1 and i_bs < i_be, 'bak markers'
s_c, e_c = line_start(cur, i_cs), line_start(cur, i_ce)
s_b, e_b = line_start(bak, i_bs), line_start(bak, i_be)
print('A) NPU 区域: 当前 %d..%d (%d B) <- 备份 %d..%d (%d B)'
      % (s_c, e_c, e_c-s_c, s_b, e_b, e_b-s_b))
npu_region = bak[s_b:e_b]
assert b'`ifndef NO_NPU' in npu_region, 'backup region missing NPU instances'
assert b'npu_cdc_top' in npu_region, 'backup region missing npu_cdc_top'
cur = cur[:s_c] + npu_region + cur[e_c:]
print('   -> 已替换, 含 6 个 ifndef 块: %d' % npu_region.count(b'`ifndef NO_NPU'))

# ---------- B) 恢复 npu_clk / npu_rst ----------
a = b'    wire clk_50m, clk_150m, clk_10m, locked;'
assert cur.count(a) == 1
cur = cur.replace(a, a + b'\n\n'
                     b'    // [NPU-RESTORE] NPU clock/reset (clk_150m from the ov5640_clk PLL)\n'
                     b'    wire npu_clk, npu_rst;\n'
                     b'    assign npu_clk = clk_150m;\n'
                     b'    assign npu_rst = !locked;')
print('B) npu_clk/npu_rst 已恢复')

# ---------- C) 注释 preprocess 两个例化 ----------
def comment_block(raw, marker, close=b');'):
    i = raw.find(marker)
    assert i != -1, 'marker not found: ' + marker.decode()
    st = line_start(raw, i)
    j = raw.find(close, i)
    assert j != -1, 'close not found for ' + marker.decode()
    en = j + len(close)
    block = raw[st:en]
    out = []
    for ln in block.split(b'\n'):
        out.append((b'//' + ln) if ln.strip() else ln)
    return raw[:st] + b'\n'.join(out) + raw[en:], block

for mk in (b'cam_prep_link #(', b'preprocess_top #('):
    cur, blk = comment_block(cur, mk)
    print('C) 已注释 %s (%d 行)' % (mk.decode(), blk.count(b'\n')+1))

# ---------- D) prep_wr_* 绑零 ----------
anchor = b'assign cam_tap_data_ready = cam_s_data_ready;'
assert cur.count(anchor) == 1, 'RAW assign anchor'
tieoff = (b'\n\n// [NPU-RESTORE] preprocess commented out: keep processed-frame write engine idle\n'
          b"assign prep_wr_cmd_valid = 1'b0;\n"
          b"assign prep_wr_cmd_addr  = 32'b0;\n"
          b"assign prep_wr_cmd_len   = 32'b0;\n"
          b"assign prep_wr_data      = 128'b0;\n"
          b"assign prep_wr_valid     = 1'b0;")
assert b'assign prep_wr_cmd_valid' not in cur, 'tieoff already present?'
cur = cur.replace(anchor, anchor + tieoff)
print('D) prep_wr_* 绑零已恢复')

open(CUR, 'wb').write(cur)

# ---------- 校验 ----------
fin = open(CUR, 'rb').read()
txt = fin.decode('latin1', 'replace')
print()
print('=== 校验 ===')
print('  npu_cdc_top 例化        :', txt.count('npu_cdc_top'))
print('  ifndef NO_NPU 块        :', txt.count('`ifndef NO_NPU'))
print('  axi_dma_read 例化       :', txt.count('axi_dma_read #('))
print('  npu_s0_out_axi_dma      :', txt.count('npu_s0_out_axi_dma'))
print('  NO_NPU 宏定义(应为0)    :', txt.count('`define NO_NPU'))
print('  npu_clk/npu_rst 赋值    :', txt.count('assign npu_clk') + txt.count('assign npu_rst'))
print('  cam_prep_link 例化(注释):', txt.count('//cam_prep_link #('))
print('  preprocess_top(注释)    :', txt.count('//preprocess_top #('))
print('  prep_wr tieoff          :', txt.count("assign prep_wr_cmd_valid = 1'b0;"))
print('  RAW 直连                :', txt.count('assign cam_s_data         = cam_tap_data;'))
print('  SID 修复                :', txt.count('u_awsid_fifo'))
print('  module/endmodule        :', txt.count('module '), txt.count('endmodule'))
assert txt.count('`define NO_NPU') == 0
assert txt.count('`ifndef NO_NPU') == 6
assert txt.count('assign npu_clk') == 1
assert txt.count('u_awsid_fifo') == 1, 'SID fix lost!'
assert txt.count("assign prep_wr_cmd_valid = 1'b0;") == 1
print('  => OK')
