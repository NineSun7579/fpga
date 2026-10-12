# -*- coding: utf-8 -*-
"""patch_rev43.py -- 50K Rev4.3: 注释 SFP1/key 实验, 恢复纯视频固件 (UTF-8/CRLF 字节级)"""
import io

P = r'C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl\hdmi_ddr_ov5640_top.v'
NL = '\r\n'
t = io.open(P, encoding='utf-8', newline='').read()
lines = t.split(NL)

START = "    reg [1:0] sfp_tx3_sync;"
END   = "    assign led_sfp_ready     = sfp_ready_sync[1] & sfp_tx3_sync[1];  // F7 = LED7"

si = [i for i, l in enumerate(lines) if l == START]
ei = [i for i, l in enumerate(lines) if l == END]
assert len(si) == 1 and len(ei) == 1 and si[0] < ei[0], (si, ei)
s, e = si[0], ei[0]

orig = lines[s:e+1]
commented = ['//[Rev4.2 注释] ' + l for l in orig]

new_code = """    // ===== [Rev4.3 2026-09-29] SFP1/key 实验已注释, 恢复纯视频固件 =====
    //  CH2(SFP0) 恒发双摄合成视频 -> 100H SFP1(QR3 CH2, D5/C5/D11/C11) 六路显示
    //  CH3(SFP1) 发原版 idle 有序集, TX_DIS 拉高禁止发射("把 sfp1 注释")
    assign sfp0_tx_disable = 1'b0;
    assign sfp1_tx_disable = 1'b1;          // [Rev4.3] SFP1 发射禁止
    wire [31:0] tx_d_l2 = sfp_tx_d;
    wire [3:0]  tx_k_l2 = sfp_tx_k;
    wire [31:0] tx_d_l3 = 32'hBC0028BC;     // [Rev4.3] CH3 原版 idle
    wire [3:0]  tx_k_l3 = 4'b1001;

    // LED 恢复视频语义(沿用上方 2FF 同步寄存器):
    //  LED1 B2 = SFP0 链路就绪(PLL+TX done+~LOS)
    //  LED2 A2 = CMOS2 配置完成   LED3 B3 = CMOS1 配置完成
    //  LED4 A3 = SFP0 侧有光(sigdet)
    //  LED6 A5 = lane2 收到 100H 对端(pcs synced & ~LOS)
    assign hdmi_int_led      = sfp_ready_sync[1] & ~sfp_los_sync[1];
    assign cmos_init_done[1] = cmos_init_done_int[1];
    assign cmos_init_done[0] = cmos_init_done_int[0];
    assign led_sfp_pcs       = sfp_det_sync[1];
    assign led_sfp_rxsync    = sfp_synced_sync[1] & ~sfp_los_sync[1];
    assign led_sfp_pll       = sfp_pll_sync[1];
    assign led_sfp_ready     = sfp_ready_sync[1];""".split('\n')

lines = lines[:s] + commented + new_code + lines[e+1:]
io.open(P, 'w', encoding='utf-8', newline='').write(NL.join(lines))
print('Rev4.3 patched: commented lines %d..%d, new block inserted' % (s+1, e+1))
