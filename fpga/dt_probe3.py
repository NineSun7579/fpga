import os, glob

# 1) phandle 0xc0000000 -> node
for p in glob.glob('/proc/device-tree/**/phandle', recursive=True) + \
         glob.glob('/proc/device-tree/**/linux,phandle', recursive=True):
    try:
        v = int.from_bytes(open(p, 'rb').read(4), 'big')
        if v == 0xc0000000:
            print('MSI-TARGET-NODE:', os.path.dirname(p))
            for f in sorted(os.listdir(os.path.dirname(p))):
                print('   prop:', f)
    except Exception:
        pass

# 2) pcie@fe260000 的子目录(节点)与属性
n = '/proc/device-tree/pcie@fe260000'
print('PCIE3 CHILD NODES:')
for f in sorted(os.listdir(n)):
    full = os.path.join(n, f)
    if os.path.isdir(full):
        print('  [node]', f, '->', sorted(os.listdir(full))[:8])

# 3) msi-map 完整内容
mm = open(n + '/msi-map', 'rb').read()
print('MSI-MAP raw:', mm.hex())

# 4) ITS 相关节点搜索
for root, dirs, files in os.walk('/proc/device-tree'):
    for d in dirs:
        if 'its' in d.lower() or 'msi' in d.lower():
            print('MSI/ITS NODE:', os.path.join(root, d))
    for f in files:
        if 'its' in f.lower():
            print('ITS PROP:', os.path.join(root, f))

# 5) /proc/interrupts 的 ITS-MSI 芯片信息
for line in open('/proc/interrupts'):
    if 'ITS' in line:
        print('IRQ:', line.strip()[:120])
