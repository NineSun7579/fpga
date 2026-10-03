# -*- coding: utf-8 -*-
"""
patch_50k_slim.py -- 50K 工程 Rev3.2 精简: 注释 DDR3+HDMI 显示链, SFP 直连 cam2_merge
"""
import io, re

BASE = r'C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test\ov5640_sfp480p_test'
TOP = BASE + r'\source\rtl\hdmi_ddr_ov5640_top.v'
FDC = BASE + r'\ov5640_sfp480p_test.fdc'
TCL = BASE + r'\build.tcl'
NL = '\r\n'

def load(p):
    return open(p, 'rb').read().decode('utf-8')

def save(p, t):
    open(p, 'wb').write(t.encode('utf-8'))

def sub1(t, old, new, tag):
    old = old.replace('\r\n', '\n').replace('\n', NL)
    new = new.replace('\r\n', '\n').replace('\n', NL)
    n = t.count(old)
    assert n == 1, ' [%s] count=%d: %r' % (tag, n, old[:60])
    return t.replace(old, new)

t = load(TOP)

# ---- P1: 端口注释 (逐行识别端口名) ----
DROP_PORTS = {'mem_rst_n','mem_ck','mem_ck_n','mem_cke','mem_cs_n','mem_ras_n','mem_cas_n',
              'mem_we_n','mem_odt','mem_a','mem_ba','mem_dqs','mem_dqs_n','mem_dq','mem_dm',
              'ddr_init_done','rstn_out','iic_tx_scl','iic_tx_sda','pix_clk','vs_out','hs_out',
              'de_out','r_out','g_out','b_out'}
lines = t.split(NL)
out = []
ndrop = 0
for ln in lines:
    st = ln.strip()
    if st.startswith('output') or st.startswith('inout'):
        code = st.split('//')[0].strip().rstrip(',').rstrip()
        m = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\s*$', code)
        if m and m.group(1) in DROP_PORTS:
            indent = ln[:len(ln) - len(ln.lstrip())]
            out.append(indent + '//[SLIM] ' + st)
            ndrop += 1
            continue
    out.append(ln)
assert ndrop == 26, 'dropped %d (expect 26)' % ndrop
t = NL.join(out)
print('P1: %d port lines commented' % ndrop)

# ---- P2: TH_1S 改 sys_clk 50M ----
t = sub1(t, "    parameter TH_1S = 27'd33000000;",
             "    parameter TH_1S = 27'd50_000_000;   // [SLIM] sys_clk 50MHz 1s", 'P2-th1s')

# ---- P3: merge o_clk/o_rst_n 改 clk2core_tx 域 ----
t = sub1(t, "        .o_clk   (  core_clk                            ),//公共域: DDR core 100MHz",
             "        .o_clk   (  clk2core_tx                        ),//公共域: [SLIM] HSST 125M(PLL 锁定后稳定)", 'P3-oclk')
t = sub1(t, "        .o_rst_n (  ddr_init_done                       ),",
             "        .o_rst_n (  fab_rst_n                          ),// [SLIM] clk2core_tx 域复位(见 SFP 块)", 'P3-orst')

# ---- P4: TESTPAT2/LINE_MARK/fram_buf 整段注释 ----
i0 = t.find('// ===== TESTPAT2: DDR 往返测试')
m = re.search(r'\.axi_rid\s*\(\s*axi_rid\s*\)\s*//\s*input\[3:0\]', t)
assert i0 > 0 and m, i0
j = t.find(');', m.start())
seg = t[i0:j+2]
t = t[:i0] + '/* [SLIM Rev3.2] fram_buf 写侧 mux + 例化整段注释(DDR 显示链停用)\n' + seg + '\n*/' + t[j+2:]

# ---- P5: sync_vg 注释 ----
i0 = t.find('//产生vga时序 720p30')
i1 = t.find('.y_act          (  y_act                )')
assert i0 > 0 and i1 > i0
j = t.find(');', i1)
seg = t[i0:j+2]
t = t[:i0] + '/* [SLIM Rev3.2] sync_vg 720p30 读出时序注释(SFP 直连 merge, 不再需要)\n' + seg + '\n*/' + t[j+2:]

# ---- P6: HDMI 输出寄存器 + ms72xx_ctl 注释, hdmi_int_led 简化 ----
i0 = t.find('//HDMI 输出寄存器')
m = re.search(r'\.iic_sda\s*\(\s*iic_sda\s*\)\s*//\s*inout\s+iic_sda', t)
assert i0 > 0 and m, i0
j = t.find(');', m.start())
seg = t[i0:j+2]
t = t[:i0] + '/* [SLIM Rev3.2] HDMI 输出寄存器 + MS7210 配置整段注释\n' + seg + '\n*/' + t[j+2:]

# hdmi_int_led 宏分支简化为恒等链路指示
old_led = "`ifdef SFP_TEST_SRC" + NL + \
"    // [SFP] B2 复用: 光口 bring-up 阶段该 LED 指示光链路就绪(原 MS7210 初始化指示暂让位)" + NL + \
"    assign hdmi_int_led = hsst_link_ready & ~sfp0_los;" + NL + \
"`else" + NL + \
"    assign hdmi_int_led = init_over_tx;" + NL + \
"`endif"
new_led = "    // [SLIM Rev3.2] B2 = SFP 链路就绪指示(PLL+TX done+收到对端光)" + NL + \
"    assign hdmi_int_led = hsst_link_ready & ~sfp0_los;"
t = sub1(t, old_led, new_led, 'P6-led')

# ---- P7: SFP 视频源直连 merge ----
old_src = """    // [SFP] 视频源选择: SFP_TEST_SRC=内部测试源(连通性/彩条), 否则=DDR 读出的双摄流
    wire [18:0] sfp_vid_data;
`ifdef SFP_TEST_SRC
    sfp_test_src #(
        .PAT ( 0 )                   // 0=位置编码测试图(连通性判误码), 1=8色彩条(彩条模式)
    ) u_sfp_test_src (
        .clk      (  pix_clk           ),
        .rst_n    (  rstn_int & locked ),
        .vid_data (  sfp_vid_data      )
    );
`else
    assign sfp_vid_data = {vs_o, hs_o, de_o, o_rgb565};
`endif

    sfp_video_tx u_sfp_video_tx(
        .vid_clk    (  pix_clk           ),
        .vid_rst_n  (  rstn_int & locked ),
        .vid_data   (  sfp_vid_data      ),"""
new_src = """    // [SLIM Rev3.2] SFP 视频源直连 cam2_merge 输出(clk2core_tx 125M 域, hs=0:
    // 协议中 hs 仅为电平转发, 100H 侧按帧首计数拆列不依赖 hs; DDR 显示链已注释)
    wire [18:0] sfp_vid_data;
    assign sfp_vid_data = {mrg_c_vs, 1'b0, mrg_c_de, mrg_c_data};

    sfp_video_tx u_sfp_video_tx(
        .vid_clk    (  clk2core_tx       ),   // [SLIM] 与 merge o_clk 同域
        .vid_rst_n  (  fab_rst_n         ),
        .vid_data   (  sfp_vid_data      ),"""
t = sub1(t, old_src, new_src, 'P7-src')

# ---- P8: heart_beat 改 sys_clk 域 ----
old_hb = """     always@(posedge core_clk) begin
        if (!ddr_init_done)
            cnt <= 27'd0;
        else if ( cnt >= TH_1S )
            cnt <= 27'd0;
        else
            cnt <= cnt + 27'd1;
     end

     always @(posedge core_clk)
        begin
        if (!ddr_init_done)
            heart_beat_led <= 1'd1;
        else if ( cnt >= TH_1S )
            heart_beat_led <= ~heart_beat_led;
    end"""
new_hb = """     // [SLIM Rev3.2] 心跳改 sys_clk 域(原 core_clk 随 DDR 链停用), 1Hz 闪烁=程序活着
     always@(posedge sys_clk) begin
        if (!rstn_int)
            cnt <= 27'd0;
        else if ( cnt >= TH_1S )
            cnt <= 27'd0;
        else
            cnt <= cnt + 27'd1;
     end

     always @(posedge sys_clk)
        begin
        if (!rstn_int)
            heart_beat_led <= 1'd1;
        else if ( cnt >= TH_1S )
            heart_beat_led <= ~heart_beat_led;
    end"""
t = sub1(t, old_hb, new_hb, 'P8-hb')

# ---- P9: DDR3_50H 例化注释 ----
i0 = t.find('DDR3_50H u_DDR3_50H')
i0 = t.rfind(NL, 0, i0) + 1
i1 = t.find(".rd_fake_stop              (1'b0               ) // input")
assert i0 > 0 and i1 > i0, (i0, i1)
j = t.find(');', i1) + 2
seg = t[i0:j]
t = t[:i0] + '/* [SLIM Rev3.2] DDR3_50H IP 例化整段注释\n' + seg + '\n*/' + t[j:]

# ---- P10: 顶部 SFP_TEST_SRC 宏注释 ----
n = t.count('`define SFP_TEST_SRC')
t = t.replace('`define SFP_TEST_SRC', '//[SLIM] `define SFP_TEST_SRC')
print('P10: SFP_TEST_SRC defines commented =', n)

# ---- P12: 文件头 Rev3.2 说明 ----
hdr = 'module hdmi_ddr_ov5640_top#('
note = ("// [SLIM Rev3.2 2026-09-29] 为加速编译注释整条 DDR3+HDMI 显示链(fram_buf/sync_vg/\n"
        "//   DDR3_50H/ms72xx/HDMI 端口与 fdc 约束), SFP 视频源直连 cam2_merge 输出(125M 域)。\n"
        "//   恢复显示链: 取消本文件中 [SLIM Rev3.2] 标记的注释、fdc 同名标记、build.tcl 被删行。\n")
t = sub1(t, hdr, note + hdr, 'P12-hdr')

save(TOP, t)
print('top.v slim patched OK')

# ================= fdc =================
f = load(FDC)
flines = f.split(NL)
fout = []
DROP_PAT = re.compile(r'define_attribute \{p:(mem_|rstn_out|iic_tx_|pix_clk|vs_out|hs_out|de_out|r_out|g_out|b_out|ddr_init_done)')
DROP_LN = re.compile(r'(create_generated_clock .*(ddrphy_clkin|ioclk)|set_clock_uncertainty .*ddrphy_clkin|set_clock_groups -name (ioclk|ddrphy))')
nd = 0
for ln in flines:
    if DROP_PAT.search(ln) or (DROP_LN.search(ln) and 'sys_clk' not in ln):
        fout.append('#[SLIM] ' + ln)
        nd += 1
    else:
        fout.append(ln)
save(FDC, NL.join(fout))
print('fdc: %d lines commented' % nd)

# ================= build.tcl =================
c = load(TCL)
DROP_FILES = ['iic_dri.v','ms72xx_ctl.v','ms7200_ctl.v','ms7210_ctl.v','fram_buf.v',
              'rd_buf.v','rd_ctrl.v','sync_vg.v','wr_buf.v','wr_cmd_trans.v','wr_ctrl.v',
              'wr_rd_ctrl_top.v','sfp_test_src.v','wr_fram_buf.idf','rd_fram_buf.idf','DDR3_50H.idf']
res = []
nc = 0
for ln in c.split(NL):
    if any(('/' + d) in ln for d in DROP_FILES):
        res.append('#[SLIM] ' + ln)
        nc += 1
    else:
        res.append(ln)
save(TCL, NL.join(res))
print('build.tcl: %d lines commented' % nc)
print('ALL DONE')
