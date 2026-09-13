import shutil

# 新增 +0x38 XDMA_REQ 只读状态寄存器：
# bit0 = 缓冲1(cam_addr_1)帧完成待取, bit1 = 缓冲2(cam_addr_2)帧完成待取
# 供主机(camview)轮询帧完成，替代 MSI 依赖。xdma_req 与 ov5640_reg 同在 video_clk 域。

# ---------------- ov5640_reg.v ----------------
P = 'source/ov5640/ov5640_reg.v'
shutil.copyfile(P, P + '.bak38')
raw = open(P, 'rb').read()

a = b'    input  [31:0]                     dbg_vsyncs\n);'
assert raw.count(a) == 1, 'port anchor'
raw = raw.replace(a, b'    input  [31:0]                     dbg_vsyncs        ,\n'
                    b'    input  [1:0]                      dbg_xdma_req\n);')

a = b"localparam REG_DBG_VSYNCS    = BASE_ADDR + 32'h34;"
assert raw.count(a) == 1, 'localparam anchor'
raw = raw.replace(a, a + b"\nlocalparam REG_DBG_XDMA_REQ  = BASE_ADDR + 32'h38;")

a = b'                    REG_DBG_VSYNCS:    rdata <= dbg_vsyncs;'
assert raw.count(a) == 1, 'case anchor'
raw = raw.replace(a, a + b'\n                    REG_DBG_XDMA_REQ:  rdata <= {{(AXI_ADDR_WIDTH-2){1\'b0}}, dbg_xdma_req};')

open(P, 'wb').write(raw)
print('patched', P)

# ---------------- ov5640_top.v ----------------
P = 'source/ov5640/ov5640_top.v'
shutil.copyfile(P, P + '.bak38')
raw = open(P, 'rb').read()

a = b'        .dbg_vsyncs            (dbg_vsyncs   )\n    );'
assert raw.count(a) == 1, 'inst anchor'
raw = raw.replace(a, b'        .dbg_vsyncs            (dbg_vsyncs   ),\n'
                     b'        .dbg_xdma_req          (xdma_req     )\n    );')

open(P, 'wb').write(raw)
print('patched', P)

for p in ('source/ov5640/ov5640_reg.v', 'source/ov5640/ov5640_top.v'):
    fin = open(p, 'rb').read()
    assert fin.count(b'dbg_xdma_req') >= 2, p
print('OK')
