import re, shutil

# 从 project.pds.bak_npu_removal 提取被删的 NPU 条目, 插回当前 project.pds
CUR = 'project/project.pds'
BAK = 'project/project.pds.bak_npu_removal'
shutil.copyfile(CUR, CUR + '.bak_pre_npu_restore')

cur = open(CUR, 'rb').read()
bak = open(BAK, 'rb').read()

def extract_blocks(raw, anchor_prefixes):
    """按括号配对提取所有匹配的 (_file ...) / (_ip ...) 块(含前导缩进)"""
    out = []
    for pref in anchor_prefixes:
        pos = 0
        while True:
            m = None
            for tag in (b'(_file "', b'(_ip "'):
                i = raw.find(tag + pref, pos)
                if i != -1 and (m is None or i < m):
                    m = i
            if m is None:
                break
            i = m
            depth, j = 0, i
            while j < len(raw):
                c = raw[j:j+1]
                if c == b'(': depth += 1
                elif c == b')':
                    depth -= 1
                    if depth == 0: break
                j += 1
            assert depth == 0, 'unbalanced: ' + repr(pref)
            end = j + 1
            # 向前吃掉行首缩进
            st = i
            while st > 0 and raw[st-1:st] in (b' ', b'\t'):
                st -= 1
            out.append(raw[st:end])
            pos = end
    return out

prefixes = [b'../source/npu/', b'../source/pcie2npu/',
            b'../source/axi_crossbar/npu_to_core_cdc_bridge.v',
            b'../source/axi_dma/axi_dma.v', b'../source/axi_dma/axi_dma_read.v',
            b'../ipcore/ins_cdc/', b'../ipcore/mul/', b'../ipcore/ov5640_cdc_fifo_D/']
blocks = extract_blocks(bak, prefixes)
print('从备份提取条目块: %d' % len(blocks))

# 插入位置: 当前文件里 preprocess 第一组 _file 之前(保持与备份相同的相对顺序区域)
anchor = cur.find(b'(_file "../source/ov5640/')
assert anchor != -1, 'ov5640 anchor not found'
# 回退到该行行首
st = anchor
while st > 0 and cur[st-1:st] not in (b'\n', b'\r'):
    st -= 1

block_text = b'\n'.join(blocks) + b'\n'
new = cur[:st] + block_text + cur[st:]
open(CUR, 'wb').write(new)

# 校验
fin = open(CUR, 'rb').read()
print('插入后 _file: %d  _ip: %d' % (fin.count(b'(_file '), fin.count(b'(_ip ')))
assert fin.count(b'(_file ') == 186, fin.count(b'(_file ')
assert fin.count(b'(_ip ') == 14, fin.count(b'(_ip ')
# 每个新增条目路径都存在?
paths = re.findall(rb'_(?:file|ip)\s+"([^"]+)"', fin)
import os
missing = []
for p in paths:
    q = p.decode().replace('/', os.sep)
    if not os.path.exists(os.path.join('project', q)):
        missing.append(p.decode())
print('缺失路径: %d' % len(missing))
for m in missing[:10]:
    print('  ', m)
assert not missing, 'missing files'
print('OK: project.pds 条目全部恢复且文件存在')
