import os, glob

# 1) __symbols__/its 的实际指向
sym = '/proc/device-tree/__symbols__/its'
if os.path.exists(sym):
    print('SYMBOL its ->', open(sym, 'rb').read().decode(errors='replace').rstrip('\x00'))

# 2) 列出所有节点的 phandle (前 40 个)
out = []
for p in glob.glob('/proc/device-tree/*/*phandle') + glob.glob('/proc/device-tree/*/*/*phandle'):
    try:
        v = int.from_bytes(open(p, 'rb').read(4), 'big')
        out.append((v, p))
    except Exception:
        pass
for v, p in sorted(out):
    print(f'phandle {v:#x} = {p}')

# 3) its 节点本身 (从符号路径) 的全部属性值
def node_dump(path):
    print('== node', path)
    try:
        for f in sorted(os.listdir(path)):
            full = os.path.join(path, f)
            if os.path.isfile(full):
                sz = os.path.getsize(full)
                data = open(full, 'rb').read(min(sz, 64))
                print(f'   {f} ({sz}B):', data.decode(errors='replace').rstrip('\x00')[:60])
    except Exception as e:
        print('   err', e)

# 找 its 节点实际位置
for root, dirs, files in os.walk('/proc/device-tree'):
    if 'msi-controller' in files:
        node_dump(root)
