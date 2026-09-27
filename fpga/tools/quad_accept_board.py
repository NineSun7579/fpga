import sys, time, signal, fcntl, json
from pathlib import Path

# [CAM4 2026-09-27] Quad-camera acceptance harness (runs on the RK3568 board).
#
# Verifies, per camera, that the capture -> CDC -> DDR path is real and routed
# to the correct frame buffer, without relying on FPS or completion counters:
#
#   phase "live"      : all four cameras free-running, both banks captured, DDR
#                       frame tag read before/after each body read;
#   phase "testpat4"  : OV5640 colour bars enabled on cam4 ONLY. The bars must
#                       appear in cam4's ping/pong and must NOT appear in any
#                       other camera's buffer (proves decode/DMA address map);
#   phase "testpat3"  : colour bars enabled on cam3 ONLY, cam4 must stay clean.
#
# Colour-bar localisation and full-frame validation are done on the host by
# tools/analyze_quad_evidence.py.
sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

assert Path('/sys/bus/pci/devices/0002:21:00.0/driver').is_symlink()

# (register base, ping, pong, index)
CAMS = [
    (0x20000000, 0x00800000, 0x00a00000, 1),
    (0x20000200, 0x00c00000, 0x00e00000, 2),
    (0x20000400, 0x01000000, 0x01200000, 3),
    (0x20000600, 0x01400000, 0x01600000, 4),
]
FRAME_BYTES = 640 * 480 * 2
TAG_OFF = FRAME_BYTES

out = Path('/tmp/quad_accept'); out.mkdir(exist_ok=True)
d = m.PciDriver()


def read(a, n):
    op = m.DmaOp(); op.ddr3_addr = a; op.total_length = n
    signal.alarm(8)
    try:
        assert fcntl.ioctl(d.fd, m.F2H_CMD, op, True) == 0
        return bytes(d.rx[:n])
    finally:
        signal.alarm(0)


def regrow(base):
    return {hex(x): d.read32(base + x) for x in range(0, 256, 16)}


def cdc(base):
    s0 = d.read32(base + 0x1c0)
    v = [d.read32(base + x) for x in (0x190, 0x1a0, 0x1b0)]
    s1 = d.read32(base + 0x1c0)
    r = dict(seq=s1, input=v[0], output=v[1], drop=v[2])
    if not (s0 == s1 and s1 >= 2):
        r.update(unstable=True, seq_before=s0)
    return r


def set_testpat(base, on):
    cam = m.CamI2c(d, base, verbose=True)
    cam.write(0x503d, 0x80 if on else 0x00)
    time.sleep(0.5)


def capture(phase, cams=None, frames=2):
    recs = []
    for base, ping, pong, idx in CAMS:
        if cams and idx not in cams:
            continue
        for f in range(frames):
            for bank, addr in enumerate((ping, pong)):
                name = '%s_cam%d_bank%d_%d' % (phase, idx, bank, f)
                before = read(addr + TAG_OFF, 16).hex()
                raw = read(addr, FRAME_BYTES)
                after = read(addr + TAG_OFF, 16).hex()
                (out / (name + '.rgb565')).write_bytes(raw)
                recs.append(dict(name=name, cam=idx, bank=bank, frame=f, phase=phase,
                                 addr=hex(addr), tag_before=before, tag_after=after))
            time.sleep(0.25)
    return recs


rows, records = [], []
try:
    # ---- chip identity for the two host-reachable SCCB cameras ----
    for base, idx in ((0x20000400, 3), (0x20000600, 4)):
        try:
            cam = m.CamI2c(d, base, verbose=True)
            hi, lo = cam.read(0x300a), cam.read(0x300b)
            print('CAM%d ID 0x300A/0x300B = 0x%02X 0x%02X' % (idx, hi, lo), flush=True)
        except Exception as e:
            print('CAM%d ID read failed: %s' % (idx, e), flush=True)

    # ---- phase A: live, all four ----
    for _ in range(40):
        rows.append(dict(t=time.monotonic(), phase='live',
                         cams=[regrow(b) for b, _, _, _ in CAMS],
                         cdc=[cdc(b) for b, _, _, _ in CAMS]))
        time.sleep(0.25)
    records += capture('live')

    # ---- phase B: colour bars on cam4 only ----
    set_testpat(0x20000600, True)
    records += capture('testpat4')
    set_testpat(0x20000600, False)

    # ---- phase C: colour bars on cam3 only ----
    set_testpat(0x20000400, True)
    records += capture('testpat3')
    set_testpat(0x20000400, False)

    print('QUAD_ACCEPT_DONE frames=%d' % len(records), flush=True)
finally:
    (out / 'registers.json').write_text(json.dumps(rows, indent=2))
    (out / 'capture.json').write_text(
        json.dumps(dict(frames=records,
                        phases=['live', 'testpat4', 'testpat3']), indent=2))
    d.close()
