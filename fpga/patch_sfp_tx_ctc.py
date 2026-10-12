#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_sfp_tx_ctc.py - 为 50K sfp_video_tx.v 添加 GE CTC skip 序列支持

修复要点:
1. 增加 8 拍相位计数器 (ctc_phase)
2. 在相位 6 强制插入 skip 有序集 {D28.2, K28.5, D28.2, K28.5}
3. skip 拍暂停 FIFO 弹出, 避免丢失像素
"""

import re
import sys

def patch_sfp_video_tx(input_file, output_file=None):
    """为 sfp_video_tx.v 添加 CTC 支持"""

    if output_file is None:
        output_file = input_file

    # 读取原文件 (字节模式，处理 GBK)
    with open(input_file, 'rb') as f:
        content = f.read()

    # 尝试解码 (GBK 或 UTF-8)
    try:
        text = content.decode('gbk')
    except:
        text = content.decode('utf-8', errors='ignore')

    # 检查是否已经打过补丁
    if 'CTC FIX' in text or 'ctc_phase' in text:
        print("[警告] 文件已包含 CTC 修复，跳过")
        return False

    # 1. 修改文件头注释
    text = text.replace(
        '// Description : 将 640x480@60 RGB565 视频流打包为 HSST(8B10B) 串行码流,\n'
        '//               经 SFP0(光口0, HSST CH2) 发送。\n'
        '//\n'
        '// ============================ 链路协议规格 (供接收端实现) =====================',

        '// Description : 将 640x480@60 RGB565 视频流打包为 HSST(8B10B) 串行码流,\n'
        '//               经 SFP0(光口0, HSST CH2) 发送。\n'
        '//\n'
        '// [2026-10-01 CTC FIX] 增加 GE CTC (Clock Tolerance Compensation) 支持:\n'
        '//   100H RX 配置为 RXPCS_CTC="GE", 要求 TX 端按 8 拍循环在第 6 拍插入\n'
        '//   skip 有序集。修复了回环测试正常但板间通信失败的问题。\n'
        '//\n'
        '// ============================ 链路协议规格 (供接收端实现) ====================='
    )

    # 2. 在协议说明中添加 skip 有序集定义
    text = text.replace(
        '//  2) 控制字 (rxk == 4\'b1001) -- 空闲/状态字, 不携带像素:\n'
        '//        txd = {8\'hBC, {de,hs,vs,5\'b0}, 8\'h28, 8\'hBC}',

        '//  2) 控制字 (rxk == 4\'b1001) -- 空闲/状态字, 不携带像素:\n'
        '//        txd = {8\'hBC, {1\'b0,hs,vs,5\'b0}, 8\'h28, 8\'hBC}'
    )

    text = text.replace(
        '//        vs/hs 电平随状态字节连续更新; 消隐期间连续发送控制字。\n'
        '//\n'
        '//  接收端重构规则:',

        '//        vs/hs 电平随状态字节连续更新; 消隐期间连续发送控制字。\n'
        '//\n'
        '//  3) [NEW] Skip 有序集 (rxk == 4\'b0101, GE CTC 每 8 拍第 6 拍强制插入):\n'
        '//        txd = {D28.2, K28.5, D28.2, K28.5} = 32\'h28BC_28BC\n'
        '//        用于 RX 侧 CTC FIFO 跳变补偿时钟容差, 100H RX 必须接收此序列。\n'
        '//\n'
        '//  接收端重构规则:'
    )

    text = text.replace(
        '//  接收端重构规则: 数据字 => 输出 2 个像素 (de=1); 控制字 => 不输出像素,\n'
        '//  锁存 vs/hs 电平。帧边界以 vs 上升沿为准, 每帧 640x480 有效像素。',

        '//  接收端重构规则: 数据字 => 输出 2 个像素 (de=1); 控制字 => 不输出像素,\n'
        '//  锁存 vs/hs 电平; skip 有序集 => CTC 处理, 不影响像素流。\n'
        '//  帧边界以 vs 上升沿为准, 每帧 640x480 有效像素。'
    )

    # 3. 在 tx_go 定义后添加 CTC 相位计数器
    ctc_counter_code = '''
    //--------------------------------------------------------------------------
    // [CTC FIX] GE 模式 8 拍相位计数器 (每 8 拍第 6 拍插入 skip)
    //--------------------------------------------------------------------------
    reg [2:0] ctc_phase;
    always @(posedge fab_clk or negedge fab_rst_n) begin
        if (!fab_rst_n)
            ctc_phase <= `UD 3'd0;
        else if (!tx_go)
            ctc_phase <= `UD 3'd0;
        else
            ctc_phase <= `UD ctc_phase + 3'd1;  // 0..7 循环
    end

    // Skip 有序集: {D28.2, K28.5, D28.2, K28.5} (GE CTC 标准)
    localparam [31:0] SKIP_WORD = 32'h28BC_28BC;
    localparam [3:0]  SKIP_K    = 4'b0101;
'''

    text = text.replace(
        '    wire tx_go = ready_sync[1];\n'
        '\n'
        '    //--------------------------------------------------------------------------\n'
        '    // 打包状态机',

        '    wire tx_go = ready_sync[1];\n' + ctc_counter_code + '\n'
        '    //--------------------------------------------------------------------------\n'
        '    // 打包状态机\n'
        '    //   [CTC FIX] 在 ctc_phase==6 时强制插入 skip, 暂停正常打包一拍。'
    )

    # 4. 修改 last_vs/last_hs 更新逻辑 (skip 拍不更新)
    text = text.replace(
        '        else if (fifo_pop) begin\n'
        '            last_vs <= `UD head_vs;\n'
        '            last_hs <= `UD head_hs;',

        '        else if (fifo_pop && (ctc_phase != 3\'d6)) begin  // [CTC FIX] skip 拍不更新\n'
        '            last_vs <= `UD head_vs;\n'
        '            last_hs <= `UD head_hs;'
    )

    # 5. 添加 FIFO 弹出门控信号
    text = text.replace(
        '    wire [31:0] idle_word = {8\'hBC, 1\'b0, last_hs, last_vs, 5\'b0, 8\'h28, 8\'hBC};\n'
        '\n'
        '    // [Rev4.3 2026-09-30]',

        '    wire [31:0] idle_word = {8\'hBC, 1\'b0, last_hs, last_vs, 5\'b0, 8\'h28, 8\'hBC};\n'
        '\n'
        '    // [CTC FIX] FIFO 弹出控制: skip 拍暂停弹出\n'
        '    wire fifo_pop_gated = fifo_pop && (ctc_phase != 3\'d6);\n'
        '\n'
        '    // [Rev4.3 2026-09-30]'
    )

    # 6. 修改主状态机: 添加 skip 拍处理
    text = text.replace(
        '        else begin\n'
        '            if (!tx_go) begin',

        '        else begin\n'
        '            // [CTC FIX] 相位 6: 强制发送 skip 有序集, 暂停正常打包\n'
        '            if (ctc_phase == 3\'d6) begin\n'
        '                txd <= `UD SKIP_WORD;\n'
        '                txk <= `UD SKIP_K;\n'
        '                // pix_pend 和 pix0 保持不变, 下拍继续处理\n'
        '            end\n'
        '            else if (!tx_go) begin'
    )

    # 7. 替换所有 fifo_pop 为 fifo_pop_gated (除了定义行)
    # 先标记定义行
    text = text.replace(
        '    wire                     fifo_pop = ~fifo_empty;',
        '    wire                     fifo_pop = ~fifo_empty;  // [CTC_FIFO_POP_ORIG]'
    )

    # 替换状态机中的 fifo_pop
    text = text.replace('else if (fifo_pop) begin', 'else if (fifo_pop_gated) begin')

    # 恢复标记
    text = text.replace('// [CTC_FIFO_POP_ORIG]', '')

    # 写回文件 (保持原编码)
    try:
        output_content = text.encode('gbk')
    except:
        output_content = text.encode('utf-8')

    with open(output_file, 'wb') as f:
        f.write(output_content)

    print(f"[成功] CTC 补丁已应用到 {output_file}")
    print("\n关键修改:")
    print("  1. 增加 8 拍相位计数器 ctc_phase")
    print("  2. 相位 6 强制插入 skip 有序集 32'h28BC_28BC")
    print("  3. skip 拍暂停 FIFO 弹出, 避免丢失像素")
    print("  4. 更新协议说明文档")
    return True

if __name__ == '__main__':
    input_file = 'ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v'

    if len(sys.argv) > 1:
        input_file = sys.argv[1]

    try:
        success = patch_sfp_video_tx(input_file)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[错误] 补丁失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
