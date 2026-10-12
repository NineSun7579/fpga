import sys

# [CAM4 2026-09-27] One-shot diagnostic row for cam3 vs cam4:
#   raw DVP edge counters (pclk / href / vsync_raw) + qualified vsync + frame
#   success + write-engine FSM state + CDC ledger, so a "frozen" camera can be
#   attributed to the sensor (raw edges stop) vs the FPGA write engine (edges
#   continue, FSM stuck).

sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

d = m.PciDriver()
r = d.read32

OFF = [
    (0x00, 'fault'), (0x10, 'pclk'), (0x20, 'vsyncs'), (0x30, 'words'),
    (0x50, 'vs_widths'), (0x60, 'fsm'), (0x70, 'aw_b'), (0x90, 'href_raw'),
    (0xd0, 'sysstat'), (0xe0, 'vsync_raw'), (0xf0, 'frames'),
    (0x190, 'cdc_in'), (0x1a0, 'cdc_out'), (0x1b0, 'cdc_drop'), (0x1c0, 'cdc_seq'),
]

for base, idx in ((0x20000400, 3), (0x20000600, 4)):
    print('--- CAM%d @0x%08X ---' % (idx, base), flush=True)
    for off, name in OFF:
        print('  +0x%03X %-10s = 0x%08X (%d)' % (off, name, r(base + off), r(base + off)), flush=True)
