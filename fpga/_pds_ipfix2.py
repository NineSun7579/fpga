import re, shutil, os

# ============================================================================
# 修复 project.pds: 3 个 _ip 条目必须位于 wgt_my_ips_src, 不是 wgt_my_design_src
# (PDS 解析源文件列表时遇到 _ip -> E: Flow-0002 File '(null)' doesn't exist)
# 用动态 widget 边界，避免硬编码偏移失效。
# ============================================================================
P = 'project/project.pds'
shutil.copyfile(P, P + '.bak_before_ipfix2')
raw = open(P, 'rb').read()

BAD = [b'../ipcore/ins_cdc/', b'../ipcore/mul/', b'../ipcore/ov5640_cdc_fifo_D/']

def widgets(raw):
    out = []
    for m in re.finditer(rb'\(_widget\s+([A-Za-z_0-9]+)', raw):
        # 块结束(括号配对)
        d = 0; j = m.start()
        while j < len(raw):
            c = raw[j:j+1]
            if c == b'(': d += 1
            elif c == b')':
                d -= 1
                if d == 0: break
            j += 1
        out.append((m.start(), j, m.group(1).decode()))
    return out

def wname(raw, off):
    n = '?'
    for s, e, name in widgets(raw):
        if s <= off <= e: return name
    return n

# ---- 1) 摘除错位的 3 个 _ip 块 ----
def line_start(r, i):
    while i > 0 and r[i-1:i] not in (b'\n', b'\r'): i -= 1
    return i

moved = []
for pref in BAD:
    idx = 0
    while True:
        i = raw.find(b'(_ip "' + pref, idx)
        if i == -1: break
        if wname(raw, i) == 'wgt_my_ips_src':
            idx = i + 1; continue
        # 括号配对
        d = 0; j = i
        while j < len(raw):
            c = raw[j:j+1]
            if c == b'(': d += 1
            elif c == b')':
                d -= 1
                if d == 0: break
            j += 1
        s = line_start(raw, i); e = j + 1
        while e < len(raw) and raw[e:e+1] in (b'\n', b'\r'): e += 1
        moved.append((pref, raw[s:e]))
        raw = raw[:s] + raw[e:]
        break
print('摘除错位块: %d' % len(moved))
for p, b in moved:
    print('  %-42s %d 字节' % (p.decode(), len(b)))
assert len(moved) == 3, 'expect 3, got %d' % len(moved)

# ---- 2) 插入 wgt_my_ips_src 的 _input 之后 ----
ws = [x for x in widgets(raw) if x[2] == 'wgt_my_ips_src']
assert len(ws) == 1, 'wgt_my_ips_src not unique'
ws_s, ws_e, _ = ws[0]
inp = raw.find(b'(_input', ws_s)
assert inp != -1 and inp < ws_e, '_input not found'
nxt = raw.find(b'(_ip "', inp)
assert nxt != -1 and nxt < ws_e, 'no _ip inside ips widget'
ins_at = line_start(raw, nxt)
payload = b'\n'.join(b for _, b in moved)
if not payload.endswith(b'\n'): payload += b'\n'
raw = raw[:ins_at] + payload + raw[ins_at:]

open(P, 'wb').write(raw)

# ---- 3) 校验 ----
fin = open(P, 'rb').read()
print()
print('=== 校验 ===')
bad = 0
for m in re.finditer(rb'\(_ip\s+"([^"]+)"', fin):
    w = wname(fin, m.start())
    if w != 'wgt_my_ips_src':
        bad += 1
        print('  错位! %-22s %s' % (w, m.group(1).decode()))
print('  _file=%d  _ip=%d  _ip错位=%d' % (
    len(re.findall(rb'_file\s+"', fin)), len(re.findall(rb'_ip\s+"', fin)), bad))

# 括号平衡
depth = 0; instr = False; esc = False
BS = chr(92); DQ = chr(34)
for ch in fin.decode('latin1'):
    if instr:
        if esc: esc = False
        elif ch == BS: esc = True
        elif ch == DQ: instr = False
        continue
    if ch == DQ: instr = True
    elif ch == '(': depth += 1
    elif ch == ')': depth -= 1
print('  括号平衡: %s' % ('OK' if depth == 0 and not instr else 'PROBLEM'))
assert bad == 0 and depth == 0
print('\nproject.pds 修复完成')
