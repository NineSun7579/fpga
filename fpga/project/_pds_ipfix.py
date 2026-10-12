import re, shutil

# ============================================================================
# 修复: 我恢复 NPU 时把 3 个 _ip 块插进了 wgt_my_design_src (design sources),
# 它们必须位于 wgt_my_ips_src 的 _input 列表里(与其他 11 个 IP 一起)。
# PDS 在 "Analyzing project file" 阶段遇到 design source widget 里的 _ip
# 条目 -> E: Flow-0002: File '(null)' doesn't exist.
# ============================================================================

P = 'project/project.pds'
shutil.copyfile(P, P + '.bak_before_ipfix')
raw = open(P, 'rb').read()

def block_at(raw, off):
    """从 '(' 处按括号配对返回整块 + 起止"""
    d = 0; j = off
    while j < len(raw):
        c = raw[j:j+1]
        if c == b'(': d += 1
        elif c == b')':
            d -= 1
            if d == 0: break
        j += 1
    assert d == 0
    return off, j + 1

def line_start(raw, i):
    while i > 0 and raw[i-1:i] not in (b'\n', b'\r'):
        i -= 1
    return i

BAD = [b'../ipcore/ins_cdc/', b'../ipcore/mul/', b'../ipcore/ov5640_cdc_fifo_D/']

# ---- 1) 收集并摘除错位的 3 个 _ip 块 ----
spans = []
for pref in BAD:
    i = raw.find(b'(_ip "' + pref)
    assert i != -1, 'not found: ' + pref.decode()
    s, e = block_at(raw, i)
    s = line_start(raw, s)
    # 吞掉尾随换行
    while e < len(raw) and raw[e:e+1] in (b'\n', b'\r'):
        e += 1
    spans.append((s, e, pref))
spans.sort()
print('摘除 3 个错位 _ip 块:')
blocks = []
for s, e, pref in reversed(spans):
    blk = raw[s:e]
    blocks.append((pref, blk))
    raw = raw[:s] + raw[e:]
    print('  %-40s %d 字节' % (pref.decode(), len(blk)))
blocks.reverse()

# ---- 2) 插入到 wgt_my_ips_src 的 _input 之后 ----
k = raw.find(b'wgt_my_ips_src')
assert k != -1, 'wgt_my_ips_src not found'
inp = raw.find(b'(_input', k)
assert inp != -1, '_input not found in ips widget'
# 该 _input 之后第一个条目的行首
nxt = raw.find(b'(_ip "', inp)
assert nxt != -1, 'no _ip in ips widget'
ins_at = line_start(raw, nxt)
payload = b'\n'.join(blk for _, blk in blocks)
if not payload.endswith(b'\n'):
    payload = payload + b'\n'
raw = raw[:ins_at] + payload + raw[ins_at:]

open(P, 'wb').write(raw)

# ---- 3) 校验 ----
fin = open(P, 'rb').read()
print()
print('=== 修复后 _ip 条目归属 ===')
bounds = [(341,'wgt_select_arch'),(620,'wgt_my_design_src'),(31118,'wgt_my_ips_src'),
          (60710,'wgt_import_logic_con_file')]
def wname(off):
    n='?'
    for b,x in bounds:
        if off>=b: n=x
    return n
bad = 0
for m in re.finditer(rb'\(_ip\s+"([^"]+)"', fin):
    w = wname(m.start())
    p = m.group(1).decode()
    flag = '' if w=='wgt_my_ips_src' else '  <== 错误位置!'
    if w!='wgt_my_ips_src': bad += 1
    print('  %-22s %s%s' % (w, p[-46:], flag))
print()
print('  _file=%d  _ip=%d' % (len(re.findall(rb'_file\s+"', fin)), len(re.findall(rb'_ip\s+"', fin))))
print('  错位条目: %d  %s' % (bad, 'OK' if bad==0 else 'PROBLEM'))

# 括号平衡
depth=0; instr=False; esc=False; BS=chr(92); DQ=chr(34)
for ch in fin.decode('latin1'):
    if instr:
        if esc: esc=False
        elif ch==BS: esc=True
        elif ch==DQ: instr=False
        continue
    if ch==DQ: instr=True
    elif ch=='(': depth+=1
    elif ch==')': depth-=1
print('  括号平衡: %s' % ('OK' if depth==0 and not instr else 'PROBLEM depth=%d'%depth))
assert bad == 0 and depth == 0
print('\n修复完成')
