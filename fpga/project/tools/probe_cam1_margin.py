import json
import fcntl
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, '/tmp')
from cam3_i2c_pt import PciDriver, DmaOp, F2H_CMD

destination = Path('/tmp/cam1_margin')
destination.mkdir(exist_ok=True)
driver = PciDriver()
try:
    for delay in (140, 145, 150, 155, 160, 165, 170, 175, 180):
        driver.write32(0x20000030, delay)
        time.sleep(0.2)
        before = driver.read32(0x200000f0)
        pixels = []
        for sample in range(10):
            pixels.append(driver.read32(0x20000190))
            time.sleep(0.05)
        after = driver.read32(0x200000f0)
        if after != before:
            operation = DmaOp()
            operation.ddr3_addr = 0x800000
            operation.total_length = 614400
            signal.alarm(8)
            try:
                if fcntl.ioctl(driver.fd, F2H_CMD, operation, True) != 0:
                    raise IOError('Frame DMA failed')
                content = bytes(driver.rx[:614400])
            finally:
                signal.alarm(0)
            (destination / ('delay%d.rgb565' % delay)).write_bytes(content)
        print(json.dumps({'delay': delay, 'frames': (after - before) & 0xffffffff,
                          'pixels': sorted(set(pixels))}), flush=True)
finally:
    driver.write32(0x20000030, 160)
    driver.close()
