import re

IMG = '/root/boot_fixed.img'
OLD = bytes.fromhex('00000000000000c00000000000001000')
NEW = bytes.fromhex('00000000000000c00000000000001000'.replace(b'0000c000'.hex(), '000000c0')) \
      if False else bytes.fromhex('00000000') + bytes.fromhex('000000c0') + bytes.fromhex('00000000') + bytes.fromhex('00001000')

d = bytearray(open(IMG, 'rb').read())
hits = [m.start() for m in re.finditer(re.escape(OLD), d)]
print('old pattern hits:', hits)
for s in hits:
    d[s:s+16] = NEW
open(IMG, 'wb').write(d)

# verify
d2 = open(IMG, 'rb').read()
n_old = len(list(re.finditer(re.escape(OLD), d2)))
n_new = len(list(re.finditer(re.escape(NEW), d2)))
print('after patch: old=', n_old, ' new=', n_new)
