#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加 sccb_diag.v 到 PDS 工程文件
"""

import re
import shutil
from datetime import datetime

def add_file_to_pds(pds_file):
    """在 PDS 工程中添加 sccb_diag.v"""

    # 备份
    backup = pds_file + '.bak_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(pds_file, backup)
    print(f"[备份] {backup}")

    # 读取
    with open(pds_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已存在
    if 'sccb_diag.v' in content:
        print("[信息] sccb_diag.v 已在工程中")
        return False

    # 找到其他 source/rtl/*.v 文件的注册位置
    # 在 sfp_video_tx.v 之后插入
    pattern = r'(\(_file "source/rtl/sfp_video_tx\.v".*?\))'

    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("[错误] 未找到 sfp_video_tx.v 条目")
        return False

    # 构造 sccb_diag.v 条目（模仿相同格式）
    new_entry = '''
    (_file "source/rtl/sccb_diag.v" + "sccb_diag"
                    (_format verilog))'''

    # 在 sfp_video_tx.v 条目后插入
    insert_pos = match.end()
    new_content = content[:insert_pos] + new_entry + content[insert_pos:]

    # 写回
    with open(pds_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[成功] 已添加 sccb_diag.v 到 {pds_file}")
    return True

if __name__ == '__main__':
    pds_file = 'ov5640_sfp480p_test.pds'

    try:
        success = add_file_to_pds(pds_file)
        exit(0 if success else 1)
    except Exception as e:
        print(f"[错误] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
