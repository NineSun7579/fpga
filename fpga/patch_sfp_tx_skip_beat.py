#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充 skip 拍处理逻辑
"""

def add_skip_beat_handling(input_file):
    """在主状态机中添加 skip 拍处理"""

    with open(input_file, 'rb') as f:
        content = f.read()

    # 检查是否已经有 skip 拍处理
    if b'if (ctc_phase == 3\'d6)' in content:
        print("[信息] skip 拍处理已存在")
        return True

    # 查找主状态机入口 "else begin" 后面紧跟 "if (!tx_go)"
    # 使用更宽松的匹配
    import re

    # 方法1: 找到 "else begin" 后第一个 "if (!tx_go)"
    pattern = rb'(        else begin\r?\n)(            if \(!tx_go\) begin)'

    replacement = rb'''\1            // [CTC FIX] Phase 6: force skip ordered set, pause normal packing
            if (ctc_phase == 3'd6) begin
                txd <= `UD SKIP_WORD;
                txk <= `UD SKIP_K;
                // pix_pend and pix0 remain unchanged, continue next beat
            end
            else \2'''

    new_content, count = re.subn(pattern, replacement, content, count=1)

    if count > 0:
        with open(input_file, 'wb') as f:
            f.write(new_content)
        print(f"[成功] 已添加 skip 拍处理逻辑 (修改 {count} 处)")
        return True
    else:
        print("[警告] 未找到匹配的主状态机入口")
        print("尝试手动查找...")

        # 显示相关代码片段
        idx = content.find(b'pix_pend   <= `UD 1\'b0;')
        if idx > 0:
            snippet = content[max(0, idx-200):idx+300]
            print("\n附近的代码:")
            print(snippet.decode('gbk', errors='ignore'))

        return False

if __name__ == '__main__':
    input_file = 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v'

    import sys
    try:
        success = add_skip_beat_handling(input_file)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[错误] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
