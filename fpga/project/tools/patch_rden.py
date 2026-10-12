#!/usr/bin/env python3
# Byte-level (GBK-safe) patch: thread a KF_RD_EN parameter from top.v through
# ov5640_top.v into vip_kf_stream's RD_EN, so the previous-frame DDR read engine
# can be disabled (RD_EN=0) for bring-up isolation. Idempotent.
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = os.path.join(ROOT, 'source', 'top.v')
OVT = os.path.join(ROOT, 'source', 'ov5640', 'ov5640_top.v')


def patch(path, subs, must_all=True):
    with open(path, 'rb') as f:
        b = f.read()
    for name, old, new in subs:
        if new in b:
            print('  [skip] %s: already applied' % name)
            continue
        n = b.count(old)
        if n != 1:
            print('  [FAIL] %s: pattern count=%d (expected 1)' % (name, n))
            if must_all:
                return False
            continue
        b = b.replace(old, new, 1)
        print('  [ok]   %s' % name)
    with open(path, 'wb') as f:
        f.write(b)
    return True


# --- ov5640_top.v: add parameter + wire into the KF instance ---
ovt_subs = [
    ('param KF_RD_EN',
     b"parameter [5:0]  KF_THR2        = 6'd20",
     b"parameter [5:0]  KF_THR2        = 6'd20,\n"
     b"parameter        KF_RD_EN       = 1'b1"),

    ('inst .RD_EN',
     b".BURST_LEN    (8)",
     b".BURST_LEN    (8),\r\n                .RD_EN        (KF_RD_EN)"),
]

# --- top.v: cam1 selects RD_EN=0 for the isolation build ---
top_subs = [
    ('cam1 KF_RD_EN',
     b".KF_EN         (1'b1)         // [VKFS] cam1 temporal filter over the DDR previous frame",
     b".KF_EN         (1'b1)         , // [VKFS] cam1 temporal filter over the DDR previous frame\n"
     b"    .KF_RD_EN      (1'b0)         // [RDTEST 2026-09-25] previous-frame DDR read DISABLED (isolation)"),
]

print('== patch ov5640_top.v ==')
ok1 = patch(OVT, ovt_subs)
print('== patch top.v ==')
ok2 = patch(TOP, top_subs)
print('RESULT:', 'OK' if (ok1 and ok2) else 'FAILED')
sys.exit(0 if (ok1 and ok2) else 1)
