#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_sfp_tx_ctc_v2.py - 为 50K sfp_video_tx.v 添加 GE CTC skip 序列支持 (字节级操作)
"""

def patch_sfp_video_tx_bytes(input_file):
    """使用字节级操作添加 CTC 支持，避免编码问题"""

    # 备份原文件
    import shutil
    backup_file = input_file + '.bak_before_ctc_' + __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(input_file, backup_file)
    print(f"[备份] {backup_file}")

    # 读取原文件（字节模式）
    with open(input_file, 'rb') as f:
        content = f.read()

    # 检查是否已经打过补丁
    if b'ctc_phase' in content or b'CTC FIX' in content:
        print("[警告] 文件已包含 CTC 修复，跳过")
        return False

    # 关键修改点的字节级查找和替换

    # 1. 在 wire tx_go 后插入 CTC 计数器代码
    marker1 = b'    wire tx_go = ready_sync[1];'

    ctc_code = b'''
    //--------------------------------------------------------------------------
    // [CTC FIX] GE mode 8-beat phase counter (insert skip at beat 6)
    //--------------------------------------------------------------------------
    reg [2:0] ctc_phase;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n)
            ctc_phase <= `UD 3'd0;
        else if (!tx_go)
            ctc_phase <= `UD 3'd0;
        else
            ctc_phase <= `UD ctc_phase + 3'd1;  // 0..7 cycle
    end

    // Skip ordered set: {D28.2, K28.5, D28.2, K28.5} (GE CTC standard)
    localparam [31:0] SKIP_WORD = 32'h28BC_28BC;
    localparam [3:0]  SKIP_K    = 4'b0101;
'''

    if marker1 in content:
        content = content.replace(marker1, marker1 + ctc_code)
        print("[OK] 插入 CTC 相位计数器")
    else:
        print("[警告] 未找到 tx_go 标记")
        return False

    # 2. 修改 last_vs/last_hs 更新条件（skip 拍不更新）
    marker2 = b'        else if (fifo_pop) begin\n            last_vs <= `UD head_vs;\n            last_hs <= `UD head_hs;'

    replacement2 = b'        else if (fifo_pop && (ctc_phase != 3\'d6)) begin  // [CTC FIX] skip beat: no update\n            last_vs <= `UD head_vs;\n            last_hs <= `UD head_hs;'

    if marker2 in content:
        content = content.replace(marker2, replacement2)
        print("[OK] 修改 last_vs/last_hs 更新逻辑")
    else:
        print("[警告] 未找到 last_vs/last_hs 更新代码")

    # 3. 添加 fifo_pop_gated 信号
    marker3 = b'    wire [31:0] idle_word = {8\'hBC, 1\'b0, last_hs, last_vs, 5\'b0, 8\'h28, 8\'hBC};'

    addition3 = b'''

    // [CTC FIX] FIFO pop control: pause at skip beat
    wire fifo_pop_gated = fifo_pop && (ctc_phase != 3'd6);'''

    if marker3 in content:
        content = content.replace(marker3, marker3 + addition3)
        print("[OK] 添加 fifo_pop_gated 信号")
    else:
        print("[警告] 未找到 idle_word 定义")

    # 4. 修改主状态机：添加 skip 拍处理
    marker4 = b'        else begin\n            if (!tx_go) begin'

    replacement4 = b'''        else begin
            // [CTC FIX] Phase 6: force skip ordered set, pause normal packing
            if (ctc_phase == 3'd6) begin
                txd <= `UD SKIP_WORD;
                txk <= `UD SKIP_K;
                // pix_pend and pix0 remain unchanged, continue next beat
            end
            else if (!tx_go) begin'''

    if marker4 in content:
        content = content.replace(marker4, replacement4)
        print("[OK] 修改主状态机（插入 skip 拍处理）")
    else:
        print("[警告] 未找到主状态机入口")

    # 5. 替换状态机中的 fifo_pop 为 fifo_pop_gated
    # 找到 "else if (fifo_pop) begin" 在状态机部分
    marker5 = b'            else if (fifo_pop) begin\n                if (!pix_pend) begin'
    replacement5 = b'            else if (fifo_pop_gated) begin\n                if (!pix_pend) begin'

    if marker5 in content:
        content = content.replace(marker5, replacement5)
        print("[OK] 替换 fifo_pop 为 fifo_pop_gated")
    else:
        print("[警告] 未找到状态机 fifo_pop 使用点")

    # 写回文件
    with open(input_file, 'wb') as f:
        f.write(content)

    print(f"\n[成功] CTC 补丁已应用到 {input_file}")
    print(f"[备份] 原文件备份为 {backup_file}")
    print("\n关键修改:")
    print("  1. 增加 8 拍相位计数器 ctc_phase (0..7 循环)")
    print("  2. 定义 skip 有序集 SKIP_WORD = 32'h28BC_28BC, SKIP_K = 4'b0101")
    print("  3. 相位 6 强制插入 skip 有序集")
    print("  4. skip 拍暂停 FIFO 弹出 (fifo_pop_gated)")
    print("  5. skip 拍不更新 last_vs/last_hs")
    return True

if __name__ == '__main__':
    input_file = 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v'

    import sys
    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    try:
        success = patch_sfp_video_tx_bytes(input_file)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[错误] 补丁失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
