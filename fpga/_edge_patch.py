import shutil

# ============================================================
# 边缘检测接入 (EDGE 2026-09-13)
#   A) cam_prep_link.v  : RAW tap 解耦(绝不反压相机)
#   B) top.v            : 恢复 cam_prep_link + preprocess_top (纯 tap 接法)
#   C) prep_regs.v      : 默认 mode=3(纯边缘) + 分辨率 640x480
# ============================================================

# ---------------- A) cam_prep_link.v ----------------
P = 'source/preprocess/cam_prep_link.v'
shutil.copyfile(P, P + '.bak_edge')
raw = open(P, 'rb').read()

a = b'    assign cam_ready = !ibusy && !iinject && raw_ready;'
assert raw.count(a) == 1, 'A1'
raw = raw.replace(a, b'    // [EDGE 2026-09-13] RAW tap decoupled: camera must NEVER be back-pressured.\n'
                     b'    // raw_ready is hardwired 1 in top (RAW bypasses this module), so this\n'
                     b'    // tap accepts every camera word; if the processing chain stalls the\n'
                     b'    // word is simply overwritten (drop) instead of stalling the camera.\n'
                     b'    assign cam_ready = raw_ready;')

a = b'    assign raw_data  = word_hold;'
assert raw.count(a) == 1, 'A2'
raw = raw.replace(a, b'    assign raw_data  = cam_data;')

a = b'    assign raw_valid = ibusy && (icnt == 3\'d7);'
assert raw.count(a) == 1, 'A3'
raw = raw.replace(a, b'    assign raw_valid = cam_valid;')

open(P, 'wb').write(raw)
print('A) cam_prep_link.v decoupled')

# ---------------- B) top.v ----------------
P = 'source/top.v'
shutil.copyfile(P, P + '.bak_edge')
raw = open(P, 'rb').read()
lines = raw.split(b'\n')

def find_line(sub, start=0):
    for i in range(start, len(lines)):
        if sub in lines[i]:
            return i
    return -1

# 新例化代码
cam_link_new = b'''// [EDGE 2026-09-13] processing-chain TAP only: RAW main path does NOT go through
// this module (see the direct-assign block below). raw_* ports are left open and
// raw_ready=1 so the tap can never back-pressure the camera.
cam_prep_link #(
    .FRAME_H (480),
    .BUFFER0 (32'h0A00_0000),
    .BUFFER1 (32'h0A10_0000)
) cam_prep_link_u (
    .clk            (axi_clk),
    .rst            (axi_rst),
    .img_width      (prep_img_width_w),
    .bypass_mode    (prep_bypass_w),
    .mode           (prep_mode_w),
    .cam_data       (cam_tap_data),
    .cam_valid      (cam_tap_data_valid),
    .cam_ready      (),
    .cam_frame_sync (cam_cmd_valid),
    .raw_data       (),
    .raw_valid      (),
    .raw_ready      (1'b1),
    .pp_data        (prep_pp_data),
    .pp_valid       (prep_pp_valid),
    .pp_ready       (prep_pp_ready),
    .pp_frame_sync  (prep_pp_fsync),
    .out_data       (prep_out_data),
    .out_valid      (prep_out_valid),
    .out_ready      (prep_out_ready),
    .out_frame_sync (prep_out_fsync),
    .wr_cmd_valid   (prep_wr_cmd_valid),
    .wr_cmd_ready   (prep_wr_cmd_ready),
    .wr_cmd_addr    (prep_wr_cmd_addr),
    .wr_cmd_len     (prep_wr_cmd_len),
    .wr_data        (prep_wr_data),
    .wr_valid       (prep_wr_valid),
    .wr_ready       (prep_wr_ready)
);'''

prep_new = b'''// [EDGE 2026-09-13] Sobel edge pipeline. reg_mode defaults to 3 (pure edge:
// white edge on black) via prep_regs; output frame is written to DDR by the
// prep2 axi_dma_write engine (crossbar S03) at 0x0A00_0000 / 0x0A10_0000.
preprocess_top #(
    .MAX_WIDTH   (1920),
    .FIFO_DEPTH  (512)
) preprocess_top_u (
    .clk            (axi_clk),
    .rst_n          (~axi_rst),
    .s_rgb565       (prep_pp_data),
    .s_valid        (prep_pp_valid),
    .s_ready        (prep_pp_ready),
    .s_frame_sync   (prep_pp_fsync),
    .m_ready        (prep_out_ready),
    .m_rgb565       (prep_out_data),
    .m_valid        (prep_out_valid),
    .m_frame_sync   (prep_out_fsync),
    .reg_bypass     (prep_bypass_w),
    .reg_mode       (prep_mode_w),
    .reg_img_width  (prep_img_width_w),
    .reg_thr_sat    (prep_thr_sat_w),
    .reg_thr_hue    (prep_thr_hue_w),
    .reg_thr_val    (prep_thr_val_w),
    .reg_thr_low    (prep_thr_low_w),
    .reg_thr_edge   (prep_thr_edge_w),
    .out_frame_start(prep_out_frame_start),
    .edge_stream_valid (prep_edge_valid),
    .edge_stream_edge  (prep_edge_bit),
    .edge_stream_center(prep_edge_center),
    .color_id_valid (prep_cid_valid),
    .color_id       (prep_cid)
);'''

def replace_block(marker, new_code):
    """替换 marker 所在注释块(向上找 OptionB 注释头, 向下找 '// );')"""
    i = find_line(marker)
    assert i != -1, marker
    h = i
    while h > 0 and not lines[h - 1].lstrip().startswith(b'// ['):
        h -= 1
    h -= 1  # 包含注释头
    j = i
    while j < len(lines) and lines[j].strip() != b'// );':
        j += 1
    assert lines[j].strip() == b'// );', 'close not found for ' + marker
    lines[h:j + 1] = new_code.split(b'\n')
    return i

# 先处理靠后的块, 再处理靠前的, 避免索引偏移
replace_block(b'// preprocess_top #(', prep_new)
replace_block(b'// cam_prep_link #(', cam_link_new)
print('B1) top.v blocks restored')

# 删除 prep_wr_* 绑零 (由 cam_prep_link 驱动)
for pat in (b'assign prep_wr_cmd_valid = 1\'b0;', b'assign prep_wr_cmd_addr  = 32\'b0;',
            b'assign prep_wr_cmd_len   = 32\'b0;', b'assign prep_wr_data      = 128\'b0;',
            b'assign prep_wr_valid     = 1\'b0;'):
    k = find_line(pat)
    assert k != -1, pat
    del lines[k]
# 删掉那行说明注释
k = find_line(b'// preprocess datapath disabled: keep the processed-frame write engine idle')
if k != -1:
    del lines[k]
print('B2) prep_wr_* tie-offs removed')

out = b'\n'.join(lines)
# 校验: 例化存在且绑零消失
assert out.count(b'cam_prep_link #(') == 1
assert out.count(b'preprocess_top #(') == 1
assert out.count(b"assign prep_wr_cmd_valid") == 0
open(P, 'wb').write(out)
print('B) top.v done')

# ---------------- C) prep_regs.v ----------------
P = 'source/preprocess/prep_regs.v'
shutil.copyfile(P, P + '.bak_edge')
raw = open(P, 'rb').read()

a = b'    localparam [11:0] D_WIDTH    = 12\'d1280;'
assert raw.count(a) == 1, 'C1'
raw = raw.replace(a, b'    localparam [11:0] D_WIDTH    = 12\'d640;   // [EDGE 2026-09-13] VGA')

a = b'    localparam [11:0] D_HEIGHT   = 12\'d720;'
assert raw.count(a) == 1, 'C2'
raw = raw.replace(a, b'    localparam [11:0] D_HEIGHT   = 12\'d480;   // [EDGE 2026-09-13] VGA')

a = b"            r_bypass <= 1'b0; r_mode <= 2'd0; r_edge_en <= 1'b1; r_color_en <= 1'b1;"
assert raw.count(a) == 1, 'C3'
raw = raw.replace(a, b"            r_bypass <= 1'b0; r_mode <= 2'd3; r_edge_en <= 1'b1; r_color_en <= 1'b1;  // [EDGE] default = pure edge view")

open(P, 'wb').write(raw)
print('C) prep_regs.v default edge mode + 640x480')

print('ALL PATCHES OK')
