import json
import sys
import time

sys.path.insert(0, '/tmp')
from cam3_i2c_pt import PciDriver

driver = PciDriver()
try:
    for delay in (0, 20, 40, 60, 80, 100, 120, 160, 200, 240):
        driver.write32(0x20000030, delay)
        time.sleep(0.3)
        first = driver.read32(0x200000f0)
        pixels = []
        for sample in range(10):
            pixels.append(driver.read32(0x20000190))
            time.sleep(0.1)
        last = driver.read32(0x200000f0)
        print(json.dumps({'delay': delay, 'completed_frames': (last - first) & 0xffffffff,
                          'input_pixels': sorted(set(pixels)),
                          'fault': hex(driver.read32(0x20000000))}), flush=True)
finally:
    driver.write32(0x20000030, 40)
    driver.close()
