import sys

sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

# On-board quad register snapshot (run after uploading cam3_i2c_pt.py to /tmp).
OFFS = (0x00, 0x10, 0x20, 0x30, 0xd0, 0xe0, 0xf0, 0x190, 0x1a0, 0x1b0, 0x1c0)
CAMS = ((0x20000000, 1), (0x20000200, 2), (0x20000400, 3), (0x20000600, 4))

d = m.PciDriver()
try:
    for base, idx in CAMS:
        row = []
        for off in OFFS:
            try:
                row.append('%#06x=%#010x' % (off, d.read32(base + off)))
            except Exception as ex:
                row.append('%#06x=ERR' % off)
        print('CAM%d' % idx)
        for r in row:
            print('   ' + r)
finally:
    d.close()
