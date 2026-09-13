import shutil

# ============================================================================
# [EDGE-FORCE 2026-09-13] 硬性固定"纯边缘"输出
#
# 为什么必须写死在 RTL 里: prep_regs 的寄存器读写通路都不可靠
#   - 读: 连续读返回上一次数据(与 tb_ovreg_axil_decode 失败同源)
#   - 写: AW/W 背靠背失步丢写(工程文档已记录为既有未修 bug)
# 实测证据: 主机写 PREP_CTRL=0x1E(busy=0,mode=3,edge_en,color_en) 后,
# 目标缓冲仍只有 44.7% 黑/白, 其余 55% 是彩色 -> mode 未被正确置 3
# (彩色只能来自 mode 0/1, 即 reg_mode 实际为 0/1)。
#
# 对策: 模式选择不再依赖 reg_mode, 输出固定为
#         edge_d1 ? WHITE : BLACK      (白边黑底)
#   同时 bypass 也写死为 0(不过滤旁路), 保证主机误写不会把画面切成原图。
# ============================================================================

P = 'source/preprocess/preprocess_top.v'
shutil.copyfile(P, P + '.bak_forceedge')
raw = open(P, 'rb').read()

# ---- 1) proc_pix 固定为纯边缘 ----
key = b'    reg [15:0] proc_pix;\n    always @* begin\n        case (reg_mode)'
i = raw.find(key)
assert i != -1, 'mode block start not found'
# 块结束: 紧接着的 "    end\n" (always 块结束)
j = raw.find(b'    end\n', raw.find(b'endcase', i))
assert j != -1, 'mode block end not found'
j += len(b'    end')
old = raw[i:j]

new = b'''    // [EDGE-FORCE 2026-09-13] Hard-wired pure-edge output.
    // reg_mode / reg_bypass are NOT used: the prep_regs read AND write paths are
    // both unreliable (continuous reads return the previous value; back-to-back
    // AW/W writes are dropped), so a host-written mode never latched reliably.
    // Result is always the Sobel view: white edge on black background.
    wire [15:0] proc_pix = edge_d1 ? WHITE : BLACK;'''
raw = raw[:i] + new + raw[j:]
print('1) proc_pix forced to pure edge')

# ---- 2) bypass 写死为 0 ----
key = b'    wire [15:0] sel_pix  = reg_bypass ? s_rgb565 : proc_pix;'
i = raw.find(key)
assert i != -1, 'bypass mux not found'
raw = raw.replace(key, b'    // [EDGE-FORCE] bypass hard-wired off: output is always the processed (edge) image\n'
                         b'    wire [15:0] sel_pix  = proc_pix;')
key2 = b'    wire        sel_valid_raw = reg_bypass ? s_valid : a_valid;'
i2 = raw.find(key2)
assert i2 != -1, 'bypass valid mux not found'
raw = raw.replace(key2, b'    wire        sel_valid_raw = a_valid;')

open(P, 'wb').write(raw)

fin = open(P, 'rb').read()
txt = fin.decode('gbk', errors='replace')
print('  case(reg_mode) present :', txt.count('case (reg_mode)'))
print('  forced proc_pix        :', 'wire [15:0] proc_pix = edge_d1 ? WHITE : BLACK;' in txt)
print('  bypass mux gone        :', txt.count('sel_pix  = reg_bypass') == 0)
print('  module/endmodule       :', txt.count('module '), txt.count('endmodule'))
assert txt.count('case (reg_mode)') == 0
assert 'wire [15:0] proc_pix = edge_d1 ? WHITE : BLACK;' in txt
assert txt.count('module ') == txt.count('endmodule')
print('ALL OK: edge output hard-wired')
