import sys
import time

sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

# Single driver session: sample cam3/cam4 PCLK + VSYNC + words over ~10 s.
d = m.PciDriver()
try:
    print('t  cam3_pclk   cam3_vs cam3_words | cam4_pclk   cam4_vs cam4_words cam4_rst/scl/sda')
    for k in range(11):
        r = {}
        for idx, base in ((3, 0x20000400), (4, 0x20000600)):
            r[idx] = (d.read32(base + 0x10), d.read32(base + 0x20),
                      d.read32(base + 0x30), d.read32(base + 0xd0))
        print('%2d %10d %8d %10d | %10d %8d %10d 0x%08x' % (
            k, r[3][0], r[3][1], r[3][2], r[4][0], r[4][1], r[4][2], r[4][3]))
        time.sleep(1.0)
finally:
    d.close()
