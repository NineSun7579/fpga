import shutil

P = 'source/top.v'
shutil.copyfile(P, P + '.bak_sidrace')
raw = open(P, 'rb').read()

# ---------- 1) 用索引定位并替换 "// latch aw_sid on AW handshake" ... "end" 块 ----------
key = b'// latch aw_sid on AW handshake'
i = raw.find(key)
assert i != -1, 'key1 not found'
# 块结束: 从 i 起找第一个 "\nend\n"
j = raw.find(b'\nend\n', i)
assert j != -1, 'end1 not found'
j += len(b'\nend')          # 指向 'end' 的最后一个字符
old1 = raw[i:j]

new1 = b'''// [SID-RACE 2026-09-13] Queue the AW slave-ID so each forged B response is routed
// back to the master that actually issued that write. A single shared register
// loses the pairing as soon as two writers (camera S01 + prep S03) have writes in
// flight together, which wedges one write engine (seen as pp_valid stuck high).
wire [AXI_ID_M_LEN-AXI_ID_LEN-1:0] aw_sid_rd;
wire                               aw_sid_valid;
reg                                aw_sid_pop;
wire                               aw_sid_push = ddr_axi_awvalid && ddr_axi_awready;
prep_sync_fifo #(.DW(AXI_ID_M_LEN-AXI_ID_LEN), .DEPTH(32), .AFULL(24)) u_awsid_fifo (
    .clk(axi_clk), .rst_n(~axi_rst),
    .wr_en(aw_sid_push),
    .wr_data(ddr_axi_awuser_id[AXI_ID_M_LEN-1 : AXI_ID_LEN]),
    .rd_en(aw_sid_pop), .rd_data(aw_sid_rd), .rd_valid(aw_sid_valid),
    .prog_full(), .cnt()
);
// legacy register kept in step (fallback only if the queue is momentarily empty)
always @(posedge axi_clk) begin
    if (axi_rst)
        ddr_axi_aw_sid <= {(AXI_ID_M_LEN - AXI_ID_LEN){1'b0}};
    else if (aw_sid_push)
        ddr_axi_aw_sid <= ddr_axi_awuser_id[AXI_ID_M_LEN-1 : AXI_ID_LEN];
end'''
raw = raw[:i] + new1 + raw[j:]
print('1) sid FIFO inserted')

# ---------- 2) 伪造 B: bid 从队列取 ----------
key = b'ddr_axi_bid_int <= {ddr_axi_aw_sid[AXI_ID_M_LEN-1 : AXI_ID_LEN], ddr_axi_wusero_id};'
i = raw.find(key)
assert i != -1, 'key2 not found'
new2 = (b'// [SID-RACE] match the SID queued for THIS write (fallback: legacy reg)\n'
        b'            ddr_axi_bid_int <= { aw_sid_valid ? aw_sid_rd : ddr_axi_aw_sid,\n'
        b'                                 ddr_axi_wusero_id };')
raw = raw[:i] + new2 + raw[i + len(key):]
print('2) forge-B uses queued SID')

# ---------- 3) pop 脉冲 ----------
key = b'assign ddr_axi_bvalid = ddr_axi_bvalid_int;'
i = raw.find(key)
assert i != -1, 'key3 not found'
new3 = (b'// [SID-RACE] pop one queued SID per forged B response\n'
        b'always @(posedge axi_clk) begin\n'
        b"    if (axi_rst) aw_sid_pop <= 1'b0;\n"
        b"    else         aw_sid_pop <= ddr_axi_wready_ddr3 && ddr_axi_wusero_last_ddr3 && aw_sid_valid;\n"
        b'end\n'
        b'\n' + key)
raw = raw[:i] + new3 + raw[i + len(key):]
print('3) pop pulse added')

open(P, 'wb').write(raw)

fin = open(P, 'rb').read()
txt = fin.decode('gbk', errors='replace')
print('  u_awsid_fifo      :', txt.count('u_awsid_fifo'))
print('  aw_sid_rd/valid/pop:', txt.count('aw_sid_rd'), txt.count('aw_sid_valid'), txt.count('aw_sid_pop'))
print('  bid from queue     :', 'aw_sid_valid ? aw_sid_rd' in txt)
print('  module/endmodule   :', txt.count('module '), txt.count('endmodule'))
assert txt.count('u_awsid_fifo') == 1
assert 'aw_sid_valid ? aw_sid_rd' in txt
assert txt.count('module ') == txt.count('endmodule')
print('ALL OK: SID race fixed')
