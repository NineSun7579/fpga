import os, glob
sym = '/proc/device-tree/__symbols__/its'
if os.path.exists(sym):
    path = open(sym, 'rb').read().decode().rstrip(chr(0))
    print('ITS NODE PATH:', path)
    full = '/proc/device-tree' + path
    if os.path.isdir(full):
        print('PROPS:', sorted(os.listdir(full)))
for p in glob.glob('/proc/device-tree/**/phandle', recursive=True) + glob.glob('/proc/device-tree/**/linux,phandle', recursive=True):
    try:
        v = int.from_bytes(open(p, 'rb').read(4), 'big')
        if v == 0xc000:
            print('PHANDLE C000 NODE:', os.path.dirname(p))
    except Exception:
        pass
n = '/proc/device-tree/pcie@fe260000'
mm = open(n + '/msi-map', 'rb').read()
print('MSI-MAP:', mm.hex())
