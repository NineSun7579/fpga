import sys,time,json,signal,fcntl
from pathlib import Path
# [CAM4 2026-09-27] Four-camera sustained capture + full-frame bank readout.
# Extends verify_cdc_sustained.py (3 cameras) to cam1..cam4.
sys.path.insert(0,'/tmp')
import cam3_i2c_pt as m
assert Path('/sys/bus/pci/devices/0002:21:00.0/driver').is_symlink()

# (base, ping, pong, label)
CAMS = [
    (0x20000000, 0x00800000, 0x00a00000, 1),
    (0x20000200, 0x00c00000, 0x00e00000, 2),
    (0x20000400, 0x01000000, 0x01200000, 3),
    (0x20000600, 0x01400000, 0x01600000, 4),
]
FRAME_BYTES = 640 * 480 * 2          # 614400
TAG_OFF = FRAME_BYTES                # 0x96000

out = Path('/tmp/quad_evidence'); out.mkdir(exist_ok=True)
d = m.PciDriver()


def read(a, n):
    op = m.DmaOp(); op.ddr3_addr = a; op.total_length = n
    signal.alarm(8)
    try:
        assert fcntl.ioctl(d.fd, m.F2H_CMD, op, True) == 0
        return bytes(d.rx[:n])
    finally:
        signal.alarm(0)


def snap():
    return [(time.monotonic(), [d.read32(b + x) for x in (0x10, 0x20, 0xf0)]) for b, _, _, _ in CAMS]


def stage_snapshot(base):
    seq0 = d.read32(base + 0x1c0)
    counts = [d.read32(base + x) for x in (0x190, 0x1a0, 0x1b0)]
    seq1 = d.read32(base + 0x1c0)
    r = dict(seq=seq1, input=counts[0], output=counts[1], drop=counts[2])
    if not (seq0 == seq1 and seq1 >= 2):
        r.update(unstable=True, seq_before=seq0, seq_after=seq1)
    return r


last_read = {}
_orig = d.read32


def traced(address):
    last_read.update(address=hex(address), t=time.monotonic())
    return _orig(address)


d.read32 = traced
rows = []
records = []
rates = []
try:
    for _ in range(121):                      # ~60 s of register sampling at 0.5 s
        row = dict(t=time.monotonic(),
                   cams=[{hex(x): d.read32(b + x) for x in range(0, 256, 16)} for b, _, _, _ in CAMS],
                   cdc=[stage_snapshot(b) for b, _, _, _ in CAMS])
        rows.append(row)
        time.sleep(0.5)
    (out / 'registers.json').write_text(json.dumps(rows, indent=2))

    dt = rows[-1]['t'] - rows[0]['t']
    for cam in range(4):
        s, e = rows[0]['cams'][cam], rows[-1]['cams'][cam]
        print('CAM', cam + 1,
              'success/s', ((e['0xf0'] - s['0xf0']) & 0xffffffff) / dt,
              'offered_pixels', sorted(set(r['cams'][cam]['0x30'] for r in rows)),
              'faults', sorted(set(hex(r['cams'][cam]['0x0']) for r in rows)),
              'overflow_delta', ((e['0xa0'] >> 16) - (s['0xa0'] >> 16)) & 65535,
              'short_delta', ((e['0xa0'] & 65535) - (s['0xa0'] & 65535)) & 65535,
              flush=True)
    for cam in range(4):
        print('CDC', cam + 1, {k: sorted(set(r['cdc'][cam][k] for r in rows))
                               for k in ('input', 'output', 'drop')}, flush=True)

    a = snap(); time.sleep(3); b = snap()
    rates = [[(y - x) & 0xffffffff for x, y in zip(u[1], v[1])] for u, v in zip(a, b)]
    rates = [[x / (v[0] - u[0]) for x in r] for r, u, v in zip(rates, a, b)]
    print('PCLK_Hz VSYNC_s FRAMES_s', rates, flush=True)

    # Full-frame bank readout, several snapshots; tag before/after proves the frame
    # advanced while the 614400-byte body was read.
    for k in range(3):
        for cam, ping, pong, _ in CAMS:
            for bank, addr in enumerate((ping, pong)):
                name = 'cam%d_bank%d_%d' % (cam, bank, k)
                before = read(addr + TAG_OFF, 16).hex()
                raw = read(addr, FRAME_BYTES)
                after = read(addr + TAG_OFF, 16).hex()
                (out / (name + '.rgb565')).write_bytes(raw)
                records.append(dict(name=name, cam=cam, bank=bank, frame=k,
                                    addr=hex(addr), tag_before=before, tag_after=after))
        time.sleep(0.3)
finally:
    (out / 'registers.json').write_text(json.dumps(rows, indent=2))
    (out / 'last_read.json').write_text(json.dumps(last_read, indent=2))
    d.close()
(out / 'capture.json').write_text(json.dumps(dict(rates=rates, frames=records), indent=2))
print('QUAD_CAPTURE_DONE', len(records), 'frames', flush=True)
