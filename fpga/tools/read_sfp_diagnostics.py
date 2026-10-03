"""Read aligned diagnostic slots in the six-recovery FPGA image only."""
import json
import sys
import time

sys.path.insert(0, '/tmp')
from cam3_i2c_pt import PciDriver

driver = PciDriver()
try:
    for sample in range(10):
        values = [driver.read32(0x20000120 + index * 16) for index in range(7)]
        status, fault5, fault6, pixels5, pixels6, states, rejects = values
        print(json.dumps({
            'sample': sample, 'time': time.monotonic(),
            'raw': [hex(value) for value in values],
            'link': dict(zip(('pll0', 'tx_done', 'rx_done', 'pcs_rx_done', 'sigdet', 'rx_enable'),
                             [bool(status & (1 << bit)) for bit in range(6)])),
            'cameras': [
                {'camera': camera, 'fault': hex(fault),
                 'overflow': bool(fault & 0x80000000),
                 'short': bool(fault & 0x40000000),
                 'dma_abort': bool(fault & 0x20000000),
                 'tag_phase': bool(fault & 0x10000000),
                 'accepted_pixels': fault & 0x0fffffff,
                 'input_pixels': pixels, 'state': (states >> shift) & 0xffff,
                 'short_count': (rejects >> shift) & 0xffff}
                for camera, fault, pixels, shift in
                ((5, fault5, pixels5, 0), (6, fault6, pixels6, 16))]
        }), flush=True)
        time.sleep(0.5)
finally:
    driver.close()
