import shutil

# ============================================================================
# [EDGE-INT 2026-09-13] 修正边缘通路的几何(HDMI 画面错乱的根因)
#
# 问题1: sobel/align16 只输出"内部"像素, 且 ccol 映射错乱(C=0 被算作有效,
#        实际输出上一行最后一列) -> 每行首 1 个错位像素, 每行长度不均匀
#        -> 总有效像素 304963, 而 cam_prep_link 期望 (W-2)*(H-2)=304964
#        -> opix 永远 != frame_pixels -> 帧永不收尾(oactive 一直为 1)
#        -> 只有第一帧被写且长度错 -> 画面完全错乱
# 问题2: 即使收尾正常, 638x478 的内容被 camview 当 640x480 显示 -> 逐行漂移
#
# 修法: 两个模块改为"每个输入像素都输出"(完整 W x H 帧), 仅当 3x3 窗口完全在
#       帧内时才可能判边(中心像素 = (row-1, col-1), 需 row>=2 && col>=2)。
#       -> 行宽恒为 W, 无剪切; frame_pixels = W*H 精确匹配; 显示几何一致。
# ============================================================================

# ---------------- A) sobel_edge.v ----------------
P = 'source/preprocess/sobel_edge.v'
shutil.copyfile(P, P + '.bak_geom')
raw = open(P, 'rb').read()

# A1: A1: add row counter + win_ok (replaces ready gate)
a = (b'    wire [11:0] w_m1   = img_width - 12\'d1;\n'
     b'    wire        col_wr = (col >= w_m1[AW-1:0]);\n')
assert raw.count(a) == 1, 'sobel A1 anchor'
raw = raw.replace(a, a + b'    reg  [11:0] row;                       // [EDGE-INT] input row index\n')

# A2: 替换 ready 定义
a = (b'    wire        ready  = (pix_cnt >= (2*img_width + 12\'d3))\n'
     b'                       && (ccol >= 2\'d1) && (ccol <= w_m1[AW-1:0] - 1\'b1);')
assert raw.count(a) == 1, 'sobel A2 anchor'
raw = raw.replace(a,
    b'    // [EDGE-INT] full-frame output: emit one beat per input pixel; window centre=(row-1,col-1),\n'
    b'    // edge only when window fully inside frame (row>=2 and col>=2), else black.\n'
    b'    wire        win_ok = (row >= 12\'d2) && (col >= 2\'d2);\n'
    b'    wire        ready  = 1\'b1;                    // keep legacy ready semantics: always 1')

# A3+A4: 复位分支与 frame_sync 分支都加 row (两处文本相同, 先统一替换)
a = (b'            col      <= 0;\n'
     b'            pix_cnt  <= 0;\n')
assert raw.count(a) == 2, ('sobel A3 anchor count', raw.count(a))
raw = raw.replace(a, b'            col      <= 0;\n            row      <= 0;\n            pix_cnt  <= 0;\n')

# A5: 递增分支加 row
a = (b'            col      <= col_wr ? {AW{1\'b0}} : col + 1\'b1;\n'
     b'            pix_cnt  <= pix_cnt + 1\'b1;\n')
assert raw.count(a) == 1, 'sobel A5 anchor'
raw = raw.replace(a, b'            col      <= col_wr ? {AW{1\'b0}} : col + 1\'b1;\n'
                     b'            row      <= col_wr ? (row + 12\'d1) : row;\n'
                     b'            pix_cnt  <= pix_cnt + 1\'b1;\n')

# A6: 输出 1:1 + 判边加 win_ok 门
a = b'            m_valid <= s_valid && ready;'
assert raw.count(a) == 1, 'sobel A6 anchor'
raw = raw.replace(a, b'            m_valid <= s_valid;                       // [EDGE-INT] 1:1 full-frame output')

a = b'            if (s_valid && ready) begin\n                m_edge   <= (mag >= {1\'b0,thr_edge});'
assert raw.count(a) == 1, 'sobel A7 anchor'
raw = raw.replace(a, b'            if (s_valid) begin\n                m_edge   <= win_ok && (mag >= {1\'b0,thr_edge});  // [EDGE-INT] no edge outside frame')

open(P, 'wb').write(raw)
print('A) sobel_edge.v -> full-frame output')

# ---------------- B) align16.v ----------------
P = 'source/preprocess/align16.v'
shutil.copyfile(P, P + '.bak_geom')
raw = open(P, 'rb').read()

a = (b'    reg [21:0]  pix_cnt;\n'
     b'    reg [AW-1:0] col;\n')
assert raw.count(a) == 1, 'align A1 anchor'
raw = raw.replace(a, a + b'    reg [11:0]  row;                      // [EDGE-INT]\n')

a = (b'    wire        ready  = (pix_cnt >= (2*img_width + 12\'d3))\n'
     b'                       && (ccol >= 2\'d1) && (ccol <= w_m1[AW-1:0] - 1\'b1);')
assert raw.count(a) == 1, 'align A2 anchor'
raw = raw.replace(a, b'    // [EDGE-INT] same structure as sobel_edge: always-on, full W x H\n'
                     b'    wire        ready  = 1\'b1;')

a = (b'            col     <= 0;\n'
     b'            pix_cnt <= 0;\n')
assert raw.count(a) == 2, ('align A3 anchor count', raw.count(a))
raw = raw.replace(a, b'            col     <= 0;\n            row     <= 0;\n            pix_cnt <= 0;\n')

a = (b'            col     <= col_wr ? {AW{1\'b0}} : col + 1\'b1;\n'
     b'            pix_cnt <= pix_cnt + 1\'b1;\n')
assert raw.count(a) == 1, 'align A5 anchor'
raw = raw.replace(a, b'            col     <= col_wr ? {AW{1\'b0}} : col + 1\'b1;\n'
                     b'            row     <= col_wr ? (row + 12\'d1) : row;\n'
                     b'            pix_cnt <= pix_cnt + 1\'b1;\n')

a = b'            m_valid <= s_valid && ready;\n            if (s_valid && ready)\n                m_pix <= w11;'
assert raw.count(a) == 1, 'align A6 anchor'
raw = raw.replace(a, b'            m_valid <= s_valid;                    // [EDGE-INT] 1:1 full frame\n            if (s_valid)\n                m_pix <= w11;')

open(P, 'wb').write(raw)
print('B) align16.v -> full-frame output')

# ---------------- C) cam_prep_link.v ----------------
P = 'source/preprocess/cam_prep_link.v'
shutil.copyfile(P, P + '.bak_geom')
raw = open(P, 'rb').read()

a = (b'    wire [31:0] frame_pixels = bypass_mode ? (img_width * FRAME_H)\n'
     b'                                           : ((img_width - 2) * (FRAME_H - 2));')
assert raw.count(a) == 1, 'link C1 anchor'
raw = raw.replace(a, b'    // [EDGE-INT] sobel/align16 now emit full W x H (no edge judgement outside frame), so expected pixel count\n'
                     b'    // equals the source, not the cropped (W-2)*(H-2).\n'
                     b'    wire [31:0] frame_pixels = img_width * FRAME_H;')

a = b'    wire frame_end = oactive && (opix == frame_pixels);'
assert raw.count(a) == 1, 'link C2 anchor'
raw = raw.replace(a, b'    wire frame_end = oactive && (opix >= frame_pixels);  // [EDGE-INT] >= tolerant compare')

open(P, 'wb').write(raw)
print('C) cam_prep_link.v -> frame_pixels = W*H, tolerant end')

print('ALL GEOMETRY PATCHES OK')
