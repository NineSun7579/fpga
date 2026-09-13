import os
hits = []
for root, dirs, files in os.walk('/proc/device-tree'):
    for fn in ('phandle', 'linux,phandle'):
        p = os.path.join(root, fn)
        if fn in files:
            try:
                v = int.from_bytes(open(p, 'rb').read(4), 'big')
                if v == 0xc0000000:
                    hits.append(root)
            except Exception:
                pass
print('TARGET NODES:', hits)
for root, dirs, files in os.walk('/proc/device-tree'):
    if 'interrupt-controller' in files:
        print('INTC:', root)
print('PCIE CHILDREN:', os.listdir('/proc/device-tree/pcie@fe260000'))
