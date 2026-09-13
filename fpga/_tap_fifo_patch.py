import shutil

# ============================================================================
# [EDGE-TAP 2026-09-13] 修复 tap 像素拆包: 加 128-bit 字 FIFO
#
# 上一版的错误: cam_ready 恒 1 后, 相机每个 128-bit 字都会立刻重置 icnt 并重载
# pix_shreg。若新字在"发射 8 像素"期间到达(相机突发), 拆包被打断 -> 像素流变
# 噪声(实测边缘缓冲无主值, 最多 6/640 重复)。
#
# 正确做法: FIFO 吸收相机突发(永不反压相机), 发射器空闲时才从 FIFO 弹一个字,
# 拆包过程读的是稳定副本 -> 不被打断, 相机也不被拖死。
# ============================================================================

P = 'source/preprocess/cam_prep_link.v'
shutil.copyfile(P, P + '.bak_wfifo')
raw = open(P, 'rb').read()

# ---- 1) 用 FIFO 例化替换旧的 cam_ready 绑定 ----
a = (b'    // [EDGE 2026-09-13] RAW tap decoupled: camera must NEVER be back-pressured.\n'
     b'    // raw_ready is hardwired 1 in top (RAW bypasses this module), so this\n'
     b'    // tap accepts every camera word; if the processing chain stalls the\n'
     b'    // word is simply overwritten (drop) instead of stalling the camera.\n'
     b'    assign cam_ready = raw_ready;')
assert raw.count(a) == 1, 'anchor1'
b = (b'    // [EDGE-TAP 2026-09-13] 128-bit word FIFO absorbs camera word bursts so the\n'
     b'    // 8-pixel emitter always unpacks a STABLE copy (a word landing mid-emission\n'
     b'    // would reset icnt and corrupt the unpack). The camera is never back-pressured.\n'
     b'    wire [127:0] wf_data;\n'
     b'    wire         wf_valid;\n'
     b'    reg          wf_rd;\n'
     b'    prep_sync_fifo #(.DW(128), .DEPTH(512), .AFULL(480)) u_wfifo (\n'
     b'        .clk(clk), .rst_n(rst_n),\n'
     b'        .wr_en(cam_valid), .wr_data(cam_data),\n'
     b'        .rd_en(wf_rd), .rd_data(wf_data), .rd_valid(wf_valid),\n'
     b'        .prog_full(), .cnt()\n'
     b'    );\n'
     b'\n'
     b'    assign cam_ready = 1\'b1;   // [EDGE-TAP] never back-pressure the camera')
raw = raw.replace(a, b)

# ---- 2) 复位分支加 wf_rd ----
a = (b'            in_word_cnt <= 17\'d0;\n'
     b'            word_hold <= 128\'d0; pix_shreg <= 128\'d0;')
assert raw.count(a) == 1, 'anchor2'
raw = raw.replace(a, b'            in_word_cnt <= 17\'d0;\n'
                     b'            word_hold <= 128\'d0; pix_shreg <= 128\'d0;\n'
                     b'            wf_rd <= 1\'b0;')

# ---- 3) else 分支开头加 wf_rd 默认值 ----
a = b'        else begin\n            // pixel emission'
assert raw.count(a) == 1, 'anchor3'
raw = raw.replace(a, b'        else begin\n            wf_rd <= 1\'b0;                  // default: no pop\n            // pixel emission')

# ---- 4) word accept 改为"从 FIFO 取字" ----
a = (b'            // word accept\n'
     b'            if (cam_valid && cam_ready) begin\n'
     b'                word_hold <= cam_data;\n'
     b'                pix_shreg <= cam_data;\n'
     b'                ibusy     <= 1\'b1;\n'
     b'                icnt      <= 3\'d0;\n'
     b'                ilast     <= (in_word_cnt == frame_words_m1);\n'
     b'            end')
assert raw.count(a) == 1, 'anchor4'
raw = raw.replace(a, b'            // [EDGE-TAP] pop one word from the FIFO when the emitter is idle\n'
                     b'            if (!ibusy && !iinject && wf_valid) begin\n'
                     b'                word_hold <= wf_data;\n'
                     b'                pix_shreg <= wf_data;\n'
                     b'                wf_rd     <= 1\'b1;      // pop it\n'
                     b'                ibusy     <= 1\'b1;\n'
                     b'                icnt      <= 3\'d0;\n'
                     b'                ilast     <= (in_word_cnt == frame_words_m1);\n'
                     b'            end')

# ---- 5) 字数统计: cam_valid (每拍写入 FIFO 即计一个) ----
a = (b'            if (cam_frame_sync)\n'
     b'                in_word_cnt <= 17\'d0;\n'
     b'            else if (cam_valid && cam_ready)\n'
     b'                in_word_cnt <= in_word_cnt + 17\'d1;')
assert raw.count(a) == 1, 'anchor5'
raw = raw.replace(a, b'            if (cam_frame_sync)\n'
                     b'                in_word_cnt <= 17\'d0;\n'
                     b'            else if (cam_valid)\n'
                     b'                in_word_cnt <= in_word_cnt + 17\'d1;')

open(P, 'wb').write(raw)

fin = open(P, 'rb').read()
assert fin.count(b'u_wfifo') == 1
assert fin.count(b"assign cam_ready = 1'b1;") == 1
assert fin.count(b'wf_rd') >= 4
assert fin.count(b'cam_valid && cam_ready') == 0
print('cam_prep_link.v: word FIFO added, unpack decoupled')
print('  wf_rd refs     :', fin.count(b'wf_rd'))
print('  wf_valid refs  :', fin.count(b'wf_valid'))
print('  module/endmodule:', fin.count(b'module '), fin.count(b'endmodule'))
