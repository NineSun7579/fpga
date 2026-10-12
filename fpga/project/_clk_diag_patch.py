import shutil

# +0x4C 时钟诊断: [31:16] clk_50m 周期计数, [1] locked, [0] button_rst_n
# 用于区分: PLL没出时钟(计数=0) / PLL出时钟但lock极性或复位问题

# ---------------- ov5640_top.v ----------------
P = 'source/ov5640/ov5640_top.v'
shutil.copyfile(P, P + '.bak_clk')
raw = open(P, 'rb').read()

a = b'    input         clk_50m               ,'
assert raw.count(a) == 1
raw = raw.replace(a, b'    input         clk_50m               ,\n'
                     b'    input         dbg_locked            ,\n'
                     b'    input         dbg_btn_rst_n         ,')

a = b'        .dbg_sys_status        (dbg_sys_status)\n    );'
assert raw.count(a) == 1
raw = raw.replace(a, b'        .dbg_sys_status        (dbg_sys_status),\n'
                     b'        .dbg_clk_status        (dbg_clk_status)\n    );')

a = b'    wire [31:0]   dbg_sys_status;'
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n    wire [31:0]   dbg_clk_status;')

a = b'ov5640_reg #('
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n'
    b"// [DBG] clk_50m activity counter + lock/button snapshot (sampled in video_clk)\n"
    b"reg [15:0] dbg_clk50_cnt;\n"
    b"always @(posedge clk_50m) dbg_clk50_cnt <= dbg_clk50_cnt + 16'd1;\n"
    b"always @(posedge video_clk) dbg_clk_status <= {dbg_clk50_cnt, dbg_locked, dbg_btn_rst_n};\n")
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- top.v ----------------
P = 'source/top.v'
shutil.copyfile(P, P + '.bak_clk')
raw = open(P, 'rb').read()
a = b'    .clk_50m       (clk_50m)        ,\n    .clk_50m_rst_n (locked & button_rst_n)        ,'
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n    .dbg_locked    (locked)         ,\n    .dbg_btn_rst_n (button_rst_n)   ,')
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_reg.v ----------------
P = 'source/ov5640/ov5640_reg.v'
shutil.copyfile(P, P + '.bak_clk')
raw = open(P, 'rb').read()

a = b'    input  [31:0]                     dbg_sys_status\n);'
assert raw.count(a) == 1
raw = raw.replace(a, b'    input  [31:0]                     dbg_sys_status      ,\n'
                     b'    input  [31:0]                     dbg_clk_status\n);')

a = b"localparam REG_DBG_SYS       = BASE_ADDR + 32'h48;"
assert raw.count(a) == 1
raw = raw.replace(a, a + b"\nlocalparam REG_DBG_CLK       = BASE_ADDR + 32'h4c;")

a = b'                    REG_DBG_SYS:       rdata <= dbg_sys_status;'
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n                    REG_DBG_CLK:       rdata <= dbg_clk_status;')
open(P, 'wb').write(raw)
print('patched', P)

for p, n in (('source/ov5640/ov5640_top.v', 5),
             ('source/top.v', 2),
             ('source/ov5640/ov5640_reg.v', 2)):
    c = open(p, 'rb').read().count(b'dbg_clk_status')
    print(p, c, 'expect', n)
    assert c == n, (p, c)
print('OK')
