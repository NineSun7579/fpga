import shutil

# top.v NPU 代码物理清理：
# 1) 删 6 个 `ifndef NO_NPU ... `endif 实例块（含保护行）
# 2) 解包 `ifdef NO_NPU ... `endif tie-off 块（保留 body）
# 3) 删 `define NO_NPU、npu_clk/npu_rst、npu_msi_req/npu_msi_grant、npu_req/req_receive、
#    cdc_s_*/cdc_out_m_* 死线网、注释掉的 npu CDC 块
# 保留：npu_reg_axi_* / npu_out_axi_* / npu_s0~s4_axi_* 声明（tie-off + crossbar 引用）、
#       tie-off 块内容、axi_crossbar_7x3 例化、MSI_NUM=5

P = 'source/top.v'
shutil.copyfile(P, P + '.bak2')
raw = open(P, 'rb').read()
lines = raw.split(b'\n')

# --- 1) remove `ifndef NO_NPU blocks ---
out, i, removed = [], 0, 0
while i < len(lines):
    if lines[i].strip() == b'`ifndef NO_NPU':
        depth, j = 1, i + 1
        while j < len(lines):
            s = lines[j].strip()
            if s.startswith(b'`ifndef') or s.startswith(b'`ifdef'):
                depth += 1
            elif s.startswith(b'`endif'):
                depth -= 1
                if depth == 0:
                    break
            j += 1
        assert depth == 0, 'unterminated ifndef NO_NPU block'
        i = j + 1
        removed += 1
    else:
        out.append(lines[i])
        i += 1
print('ifndef NO_NPU blocks removed:', removed)
assert removed == 6, removed
lines = out

# --- 2) unwrap `ifdef NO_NPU tie-off ---
idx = [k for k, l in enumerate(lines) if l.strip() == b'`ifdef NO_NPU']
assert len(idx) == 1, idx
i = idx[0]
depth, j = 1, i + 1
while j < len(lines):
    s = lines[j].strip()
    if s.startswith(b'`ifndef') or s.startswith(b'`ifdef'):
        depth += 1
    elif s.startswith(b'`endif'):
        depth -= 1
        if depth == 0:
            break
    j += 1
assert depth == 0
del lines[j]
del lines[i]
print('ifdef NO_NPU tie-off unwrapped')

# --- 3) exact-pattern line drops ---
def drop(pattern, expect=1):
    global lines
    hits = [k for k, l in enumerate(lines) if pattern in l]
    assert len(hits) == expect, (pattern, hits)
    for k in reversed(hits):
        del lines[k]

drop(b'`define NO_NPU')                          # 源选择注释区
drop(b'wire npu_clk, npu_rst;')
drop(b'assign npu_clk = clk_150m;')
drop(b'assign npu_rst = !locked;')
drop(b'wire npu_msi_req, npu_msi_grant;')
drop(b'assign npu_msi_grant = msi_grant[2];')
drop(b'wire                    npu_req        ;')
drop(b'wire                    npu_req_receive;')

# msi_req 拼接改常数 0（MSI 向量槽位不变）
k = [k for k, l in enumerate(lines) if b'assign msi_req = {1\'d0, npu_msi_req, cam_irq};' in l]
assert len(k) == 1, k
lines[k[0]] = lines[k[0]].replace(b'npu_msi_req', b'1\'b0')
print('msi_req concat fixed')

# cdc_s_*/cdc_out_m_* 死线网块（CMD_S2MM 注释行 → cdc_out_m_cmd_ready 行）
a = [k for k, l in enumerate(lines) if b'CMD_S2MM CMDMM2S' in l]
assert len(a) == 1, a
bnd = [k for k, l in enumerate(lines) if b'cdc_out_m_cmd_ready' in l]
assert len(bnd) == 1, bnd
assert bnd[0] > a[0]
del lines[a[0]:bnd[0] + 1]
print('cdc dead wires removed')

# 注释掉的 npu_req_cdc / npu_grant_cdc 块
idxs = [k for k, l in enumerate(lines) if b'ips2l_rst_sync_v1_3' in l]
assert len(idxs) == 2, idxs
ends = [k for k in range(idxs[1], len(lines)) if lines[k].strip() == b'// );']
assert ends, 'no closing comment found'
del lines[idxs[0]:ends[0] + 1]
print('commented npu cdc blocks removed')

open(P, 'wb').write(b'\n'.join(lines))

# --- final sanity ---
fin = open(P, 'rb').read()
assert b'NO_NPU' not in fin, 'NO_NPU still present'
assert b'npu_cdc_top' not in fin
assert b'axi_dma_read' not in fin
assert b'npu_s0_out_axi_dma' not in fin
import re
leftover = sorted(set(re.findall(rb'npu_[A-Za-z0-9_]*', fin)))
print('leftover npu_* names:', leftover)
print('lines:', len(fin.split(b'\n')))
