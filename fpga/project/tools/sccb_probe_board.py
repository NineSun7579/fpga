import sys
import time

sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

# Repeated SCCB probe: compare cam3 (known-good, streaming) with cam4.
d = m.PciDriver()


def probe(name, base):
    cam = m.CamI2c(d, base, verbose=False)
    print('--- %s (base %#x) ---' % (name, base))
    for k in range(3):
        try:
            st_before = d.read32(base + 0x120)
            hi = cam.read(0x300A)
            st_hi = d.read32(base + 0x120)
            lo = cam.read(0x300B)
            st_lo = d.read32(base + 0x120)
            print('  try%d id=0x%02X 0x%02X  stat(before/afterHi/afterLo)=0x%08x 0x%08x 0x%08x'
                  % (k, hi, lo, st_before, st_hi, st_lo))
        except Exception as e:
            print('  try%d EXC %s: %s' % (k, type(e).__name__, e))
        time.sleep(0.2)


try:
    probe('CAM3', 0x20000400)
    probe('CAM4', 0x20000600)
finally:
    d.close()
