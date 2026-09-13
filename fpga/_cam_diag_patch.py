import shutil

# 相机诊断补丁：+0x3C {NACK计数[31:16], ID_H[15:8], ID_L[7:0]}，+0x44 PCLK活动计数
# ID 期望 0x5640；NACK=0 说明 SCCB 每笔都被从机应答；PCLK 计数走动说明相机在输出像素时钟

# ---------------- ov5640.v ----------------
P = 'source/ov5640/ov5640/ov5640.v'
shutil.copyfile(P, P + '.bak_diag')
raw = open(P, 'rb').read()

a = b'    output [DATA_WIDTH-1:0]    video_data         /*synthesis PAP_MARK_DEBUG="1"*/   //\xd3\xd0\xd0\xa7\xca\xfd\xbe\xdd   '
assert raw.count(a) == 1, 'port anchor miss'
raw = raw.replace(a, a + b',\n'
                  b'    output reg [31:0]         dbg_i2c_status     ,  //[31:16]NACK ops [15:8]ID_H [7:0]ID_L\n'
                  b'    output reg [31:0]         dbg_pclk_cnt          //free-running pclk counter')

a = b'    .i2c_ack    (),            //I2C'
assert raw.count(a) == 1, 'ack anchor miss'
raw = raw.replace(a, b'    .i2c_ack    (i2c_ack)     ,            //I2C')

a = b'wire            cam_init_done   ;   //'
assert raw.count(a) == 1, 'wire anchor miss'
raw = raw.replace(a, b'wire            cam_init_done   ;   //\xc9\xe3\xcf\xf1\xcd\xb7\xb3\xf6\xb3\xf5\xca\xbc\xbb\xaf\xcd\xea\xb3\xc9\xd0\xc5\xba\xc5 \n'
                     b'wire            i2c_ack         ;   //[DBG] 0:acked 1:nacked')

a = b'cmos_capture #('
assert raw.count(a) == 1, 'cap anchor miss'
dbg_blk = (b'// [DBG] SCCB health: latch first two read bytes (OV5640 ID 0x56,0x40) + NACK op count\n'
           b'reg [3:0] dbg_rd_cnt;\n'
           b'always @(posedge dri_clk or negedge rst_n) begin\n'
           b'    if(!rst_n) begin\n'
           b'        dbg_rd_cnt     <= 4\'d0;\n'
           b'        dbg_i2c_status <= 32\'d0;\n'
           b'    end\n'
           b'    else if(i2c_done) begin\n'
           b'        if(i2c_ack) dbg_i2c_status[31:16] <= dbg_i2c_status[31:16] + 16\'d1;\n'
           b'        if(i2c_rh_wl && (dbg_rd_cnt < 4\'d2)) begin\n'
           b'            dbg_rd_cnt <= dbg_rd_cnt + 4\'d1;\n'
           b'            if(dbg_rd_cnt == 4\'d0) dbg_i2c_status[15:8] <= i2c_data_r;\n'
           b'            else                   dbg_i2c_status[7:0]  <= i2c_data_r;\n'
           b'        end\n'
           b'    end\n'
           b'end\n'
           b'\n'
           b'// [DBG] pclk activity counter (pclk domain, read twice to check delta)\n'
           b'always @(posedge cam_pclk) dbg_pclk_cnt <= dbg_pclk_cnt + 32\'d1;\n'
           b'\n')
raw = raw.replace(a, dbg_blk + a)
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_top.v ----------------
P = 'source/ov5640/ov5640_top.v'
shutil.copyfile(P, P + '.bak_diag')
raw = open(P, 'rb').read()

a = b'        .video_data         (video_data )   //'
assert raw.count(a) == 1, 'top ov5640 inst anchor miss'
raw = raw.replace(a, a + b',\n'
                  b'        .dbg_i2c_status     (dbg_i2c_status),\n'
                  b'        .dbg_pclk_cnt       (dbg_pclk_cnt )')

a = b'        .dbg_xdma_req          (xdma_req     )\n    );'
assert raw.count(a) == 1, 'top reg inst anchor miss'
raw = raw.replace(a, b'        .dbg_xdma_req          (xdma_req     ),\n'
                     b'        .dbg_i2c_status        (dbg_i2c_status),\n'
                     b'        .dbg_pclk_cnt          (dbg_pclk_cnt )\n    );')

a = b'    wire [1 : 0]  xdma_req  ;  '
assert raw.count(a) == 1, 'top wire anchor miss'
raw = raw.replace(a, a + b'\n    wire [31:0]   dbg_i2c_status;\n    wire [31:0]   dbg_pclk_cnt;')
open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_reg.v ----------------
P = 'source/ov5640/ov5640_reg.v'
shutil.copyfile(P, P + '.bak_diag')
raw = open(P, 'rb').read()

a = b'    input  [1:0]                      dbg_xdma_req\n);'
assert raw.count(a) == 1, 'reg port anchor miss'
raw = raw.replace(a, b'    input  [1:0]                      dbg_xdma_req        ,\n'
                     b'    input  [31:0]                     dbg_i2c_status      ,\n'
                     b'    input  [31:0]                     dbg_pclk_cnt\n);')

a = b"localparam REG_DBG_XDMA_REQ  = BASE_ADDR + 32'h38;"
assert raw.count(a) == 1, 'reg lp anchor miss'
raw = raw.replace(a, a + b"\nlocalparam REG_DBG_I2C_ID    = BASE_ADDR + 32'h3c;\n"
                         b"localparam REG_DBG_PCLK_CNT  = BASE_ADDR + 32'h44;")

a = b'                    REG_DBG_XDMA_REQ:  rdata <='
assert raw.count(a) == 1, 'reg case anchor miss'
i = raw.find(a)
j = raw.find(b'\n', i)
line = raw[i:j]
raw = raw[:j] + (b"\n                    REG_DBG_I2C_ID:    rdata <= dbg_i2c_status;"
                 b"\n                    REG_DBG_PCLK_CNT:  rdata <= dbg_pclk_cnt;") + raw[j:]
open(P, 'wb').write(raw)
print('patched', P)

# sanity
r1 = open('source/ov5640/ov5640/ov5640.v','rb').read()
r2 = open('source/ov5640/ov5640_top.v','rb').read()
r3 = open('source/ov5640/ov5640_reg.v','rb').read()
print('ov5640.v counts:', r1.count(b'dbg_i2c_status'), r1.count(b'dbg_pclk_cnt'), r1.count(b'i2c_ack'))
print('top.v    counts:', r2.count(b'dbg_i2c_status'), r2.count(b'dbg_pclk_cnt'))
print('reg.v    counts:', r3.count(b'dbg_i2c_status'), r3.count(b'dbg_pclk_cnt'))
assert b"32'h3c" in r3 and b"32'h44" in r3
print('OK')
