import shutil

# +0x48 系统状态寄存器（区分"I2C没跑"与"SDA粘低"）：
#   [31:16] i2c_exec_cnt  SCCB 事务发起总数 (cfg FSM 每笔 +1)
#   [5]     sda_level     读时刻 SDA 线电平
#   [4]     scl_level     读时刻 SCL 线电平
#   [1]     locked        ov5640_clk PLL lock
#   [0]     cam_rst_n     相机复位脚当前值

# ---------------- ov5640.v ----------------
P = 'source/ov5640/ov5640/ov5640.v'
shutil.copyfile(P, P + '.bak_sys')
raw = open(P, 'rb').read()

a = b'    output reg [31:0]         dbg_pclk_cnt          //free-running pclk counter'
assert raw.count(a) == 1
raw = raw.replace(a, b'    output reg [31:0]         dbg_pclk_cnt          ,//free-running pclk counter\n'
                     b'    output reg [31:0]         dbg_sys_status        //[31:16]exec_cnt [5]sda [4]scl [1]lock [0]rst_n')

a = b"always @(posedge cam_pclk) dbg_pclk_cnt <= dbg_pclk_cnt + 32'd1;"
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n'
    b"// [DBG] i2c transaction counter + bus level snapshot\n"
    b"wire dbg_sda_lvl = cam_sda;\n"
    b"wire dbg_scl_lvl = cam_scl;\n"
    b"reg [15:0] dbg_exec_cnt;\n"
    b"always @(posedge dri_clk or negedge rst_n) begin\n"
    b"    if(!rst_n) dbg_exec_cnt <= 16'd0;\n"
    b"    else if(i2c_exec) dbg_exec_cnt <= dbg_exec_cnt + 16'd1;\n"
    b"end\n"
    b"always @(posedge dri_clk) dbg_sys_status <= {dbg_exec_cnt, 2'b00, dbg_sda_lvl, dbg_scl_lvl,\n"
    b"                                            1'b0, cam_rst_n};")
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_top.v ----------------
P = 'source/ov5640/ov5640_top.v'
shutil.copyfile(P, P + '.bak_sys')
raw = open(P, 'rb').read()

a = b'        .dbg_pclk_cnt       (dbg_pclk_cnt )'
assert raw.count(a) == 1
raw = raw.replace(a, a + b',\n        .dbg_sys_status     (dbg_sys_status)')

a = b'        .dbg_pclk_cnt          (dbg_pclk_cnt )\n    );'
assert raw.count(a) == 1
raw = raw.replace(a, b'        .dbg_pclk_cnt          (dbg_pclk_cnt ),\n'
                     b'        .dbg_sys_status        (dbg_sys_status)\n    );')

a = b'    wire [31:0]   dbg_pclk_cnt;'
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n    wire [31:0]   dbg_sys_status;')
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_reg.v ----------------
P = 'source/ov5640/ov5640_reg.v'
shutil.copyfile(P, P + '.bak_sys')
raw = open(P, 'rb').read()

a = b'    input  [31:0]                     dbg_pclk_cnt\n);'
assert raw.count(a) == 1
raw = raw.replace(a, b'    input  [31:0]                     dbg_pclk_cnt        ,\n'
                     b'    input  [31:0]                     dbg_sys_status\n);')

a = b"localparam REG_DBG_PCLK_CNT  = BASE_ADDR + 32'h44;"
assert raw.count(a) == 1
raw = raw.replace(a, a + b"\nlocalparam REG_DBG_SYS       = BASE_ADDR + 32'h48;")

a = b'                    REG_DBG_PCLK_CNT:  rdata <= dbg_pclk_cnt;'
assert raw.count(a) == 1
raw = raw.replace(a, a + b'\n                    REG_DBG_SYS:       rdata <= dbg_sys_status;')
open(P, 'wb').write(raw)
print('patched', P)

for p, n in (('source/ov5640/ov5640/ov5640.v', 5),
             ('source/ov5640/ov5640_top.v', 5),
             ('source/ov5640/ov5640_reg.v', 3)):
    c = open(p, 'rb').read().count(b'dbg_sys_status')
    print(p, c)
    assert c == n, (p, c)
print('OK')
