"""Run alone on RK3568: DDR read capacity and read-only sensor registers."""
import fcntl
import json
import signal
import statistics
import time
from cam3_i2c_pt import PciDriver, DmaOp, F2H_CMD, CamI2c

d = PciDriver()
report = {'capacity_only': True, 'transfers': [], 'sensor_registers': {}}
try:
    for length, count, copy in [(16, 120, True), (614400, 240, True),
                                (614416, 240, True), (614416, 240, False)]:
        durations = []
        start = time.perf_counter()
        for i in range(count):
            op = DmaOp()
            op.ddr3_addr = (0x800000 + (i % 6) * 0x400000
                            + (614400 if length == 16 else 0))
            op.total_length = length
            signal.alarm(3)
            t = time.perf_counter()
            try:
                if fcntl.ioctl(d.fd, F2H_CMD, op, True) != 0:
                    raise IOError('DMA failed')
                # Include user copy to approximate the viewer's payload path.
                if copy:
                    data = d.rx[:length]
            finally:
                signal.alarm(0)
            durations.append((time.perf_counter() - t) * 1000)
        elapsed = time.perf_counter() - start
        report['transfers'].append({
            'bytes': length, 'count': count, 'seconds': elapsed, 'user_copy': copy,
            'MB_per_second': length * count / elapsed / 1e6,
            'frames_per_second': count / elapsed,
            'median_ms': statistics.median(durations),
            'p95_ms': sorted(durations)[int(len(durations) * .95)],
        })
    for camera, base in [(3, 0x20000400), (4, 0x20000600)]:
        cam = CamI2c(d, base, verbose=False)
        regs = {}
        for addr in [0x300a, 0x300b, 0x3034, 0x3035, 0x3036, 0x3037,
                     0x3108, 0x380c, 0x380d, 0x380e, 0x380f, 0x3a00,
                     0x3a02, 0x3a03, 0x3a14, 0x3a15, 0x3503]:
            value, nack = cam.xact(1, addr)
            regs[hex(addr)] = {'value': value, 'nack': nack}
        report['sensor_registers'][camera] = regs
finally:
    d.close()
print(json.dumps(report, indent=2))
