import os
its = '/proc/device-tree/interrupt-controller@fd400000/interrupt-controller@fd440000'
ph = open(its + '/phandle', 'rb').read()
print('ITS phandle raw hex:', ph.hex())
print('ITS phandle value:', int.from_bytes(ph, 'big'))
mm = open('/proc/device-tree/pcie@fe260000/msi-map', 'rb').read()
print('msi-map:', mm.hex())
print('msi-map phandle field:', int.from_bytes(mm[4:8], 'big'))
# 全表里最大的 phandle
mx = 0
for p in glob.glob('/proc/device-tree/**/phandle', recursive=True):
    try:
        v = int.from_bytes(open(p, 'rb').read(4), 'big')
        if v > mx: mx = v
    except Exception:
        pass
print('max phandle in DT: 0x%x' % mx)
