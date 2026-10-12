import sys

sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

# REG_DBG_I2C_ID = BASE+0x60: [31:16]=NACK count, [15:8]=1st read byte (ID_H),
# [7:0]=2nd read byte (ID_L).  Expect 0x56/0x40 for OV5640.
# REG_DBG_SYS = BASE+0x70, REG_DBG_AXI_NOW = BASE+0xd0 (exec_cnt/sda/scl/rst_n).
CAMS = ((0x20000000, 1), (0x20000200, 2), (0x20000400, 3), (0x20000600, 4))

d = m.PciDriver()
try:
    for base, idx in CAMS:
        i2c = d.read32(base + 0x60)
        sysr = d.read32(base + 0x70)
        now = d.read32(base + 0xd0)
        nack = (i2c >> 16) & 0xFFFF
        idh = (i2c >> 8) & 0xFF
        idl = i2c & 0xFF
        print('CAM%d I2C_ID=0x%08x (nack=%d id=0x%02x 0x%02x)  SYS=0x%08x  NOW=0x%08x'
              % (idx, i2c, nack, idh, idl, sysr, now))
finally:
    d.close()
