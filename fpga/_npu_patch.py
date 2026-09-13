import shutil, sys

SRC = 'source/top.v'
BAK = 'source/top.v.bak_before_nonpu'
shutil.copyfile(SRC, BAK)

raw = open(SRC, 'rb').read()
lines = raw.split(b'\n')

DEFINE = [b' `define NO_NPU', b'']

TIE = [
    b'`ifdef NO_NPU',
    b'// ===== NO_NPU: NPU hierarchy removed, tie off crossbar-facing NPU ports =====',
    b'// S02 write (npu_out) + S02 read (npu_s0)',
    b'assign npu_out_axi_awvalid = 1\'b0;',
    b'assign npu_out_axi_wvalid  = 1\'b0;',
    b'assign npu_out_axi_bready  = 1\'b1;',
    b'assign npu_s0_axi_arvalid  = 1\'b0;',
    b'assign npu_s0_axi_rready   = 1\'b1;',
    b'// S03 read (npu_s1) ; S03 write (prep2) stays active',
    b'assign npu_s1_axi_arvalid  = 1\'b0;',
    b'assign npu_s1_axi_rready   = 1\'b1;',
    b'// S04/S05/S06 read (npu_s2/s3/s4)',
    b'assign npu_s2_axi_arvalid  = 1\'b0;',
    b'assign npu_s2_axi_rready   = 1\'b1;',
    b'assign npu_s3_axi_arvalid  = 1\'b0;',
    b'assign npu_s3_axi_rready   = 1\'b1;',
    b'assign npu_s4_axi_arvalid  = 1\'b0;',
    b'assign npu_s4_axi_rready   = 1\'b1;',
    b'// M02 (NPU register window) response inputs',
    b'assign npu_reg_axi_awready = 1\'b1;',
    b'assign npu_reg_axi_wready  = 1\'b1;',
    b'assign npu_reg_axi_bid     = {AXI_ID_LEN{1\'b0}};',
    b'assign npu_reg_axi_bresp   = 2\'b00;',
    b'assign npu_reg_axi_bvalid  = 1\'b0;',
    b'wire   [AXI_ID_LEN-1:0]   npu_reg_axi_rid;',
    b'wire   [AXI_DATA_LEN-1:0] npu_reg_axi_rdata;',
    b'wire   [1:0]              npu_reg_axi_rresp;',
    b'wire                      npu_reg_axi_rlast;',
    b'wire                      npu_reg_axi_rvalid;',
    b'wire                      npu_reg_axi_arready;',
    b'assign npu_reg_axi_arready = 1\'b1;',
    b'assign npu_reg_axi_rid     = {AXI_ID_LEN{1\'b0}};',
    b'assign npu_reg_axi_rdata   = {AXI_DATA_LEN{1\'b0}};',
    b'assign npu_reg_axi_rresp   = 2\'b00;',
    b'assign npu_reg_axi_rlast   = 1\'b0;',
    b'assign npu_reg_axi_rvalid  = 1\'b0;',
    b'`endif',
]

before = {
    1349: [b'`ifndef NO_NPU'],
    1507: [b'`ifndef NO_NPU'],
    1598: [b'`ifndef NO_NPU'],
    1661: [b'`ifndef NO_NPU'],
    1724: [b'`ifndef NO_NPU'],
    1787: [b'`ifndef NO_NPU'],
}
after = {
    5:    DEFINE,
    1440: [b'`endif'],
    1578: [b'`endif'],
    1638: [b'`endif'],
    1701: [b'`endif'],
    1764: [b'`endif'],
    1827: [b'`endif'] + TIE,
}

out = []
for idx, ln in enumerate(lines, 1):
    if idx in before:
        out.extend(before[idx])
    out.append(ln)
    if idx in after:
        out.extend(after[idx])

open(SRC, 'wb').write(b'\n'.join(out))
print('patched', SRC, 'lines', len(lines), '->', len(out))
