import sys, json, zlib
from pathlib import Path
import numpy as np

# [CAM4 2026-09-27] Host-side analysis of tools/quad_accept_board.py evidence.
#
# For every captured frame:
#   * full-frame validation: byte length, RGB565 decode, content (non-black
#     fraction), CRC32, uniformity, and frame-advance via the DDR tag read
#     before/after the body read;
#   * colour-bar localisation: detects the vertical bars (OV5640 test pattern),
#     reports edge x-positions, per-bar mean RGB and the saturated-colour bbox;
#   * cross-camera distinctness within each phase (pairwise MAD) so duplicated
#     or aliased buffers are rejected.
#
# Phase verdicts (from tools/quad_accept_board.py):
#   testpat4 -> cam4 must show the bars, cam3 must not;
#   testpat3 -> cam3 must show the bars, cam4 must not.
#
# Usage: python tools/analyze_quad_evidence.py [evidence_dir]
ROOT = Path(__file__).resolve().parents[1]
EV = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'tp' / 'quad_accept'
W, H = 640, 480
FRAME_BYTES = W * H * 2


def decode(buf):
    a = np.frombuffer(buf, dtype=np.uint8)[: FRAME_BYTES].reshape(H, W, 2).astype(np.uint16)
    w = a[:, :, 0] | (a[:, :, 1] << 8)
    r = ((w >> 11) & 0x1F).astype(np.float32) * (255.0 / 31)
    g = ((w >> 5) & 0x3F).astype(np.float32) * (255.0 / 63)
    b = (w & 0x1F).astype(np.float32) * (255.0 / 31)
    return np.stack([r, g, b], axis=2)


def find_bars(img, band=(120, 360)):
    y0, y1 = band
    col = img[y0:y1].mean(axis=0)
    grad = np.abs(np.diff(col, axis=0)).sum(axis=1)
    gs = np.convolve(grad, np.ones(5) / 5, mode='same')
    thr = max(8.0, gs.mean() + 1.5 * gs.std())
    edges = []
    for x in range(2, len(gs) - 2):
        if gs[x] >= thr and gs[x] == gs[max(0, x - 2):x + 3].max():
            if not edges or x - edges[-1] > 12:
                edges.append(x)
    bounds = [0] + edges + [W]
    bars = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a < 8:
            continue
        seg = img[y0:y1, a:b].reshape(-1, 3).mean(axis=0)
        bars.append(dict(x0=a, x1=b, w=b - a, rgb=[round(float(v), 1) for v in seg]))
    return edges, bars


def testpat_like(edges, bars, img):
    """A synthetic 8-bar pattern: 8 bars, near-equal widths, sharp edges, and it
    fills the full frame height (unlike a chart sitting in a live scene)."""
    if len(bars) != 8:
        return False
    widths = np.array([b['w'] for b in bars], dtype=float)
    if widths.std() > 12:
        return False
    # bars must reach near the top and bottom of the frame
    col_top = img[2:20].std(axis=(0, 1)).mean()
    col_bot = img[H - 20:H - 2].std(axis=(0, 1)).mean()
    return bool(col_top > 20 and col_bot > 20)


def color_bbox(img):
    mx = img.max(axis=2); mn = img.min(axis=2)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    mask = (sat > 0.35) & (mx > 40)
    if mask.sum() < 500:
        return None, int(mask.sum())
    ys, xs = np.where(mask)
    return dict(x0=int(xs.min()), x1=int(xs.max()), y0=int(ys.min()), y1=int(ys.max())), int(mask.sum())


def main():
    cap = json.loads((EV / 'capture.json').read_text())
    regs = json.loads((EV / 'registers.json').read_text()) if (EV / 'registers.json').exists() else []
    frames, cache = [], {}
    for rec in cap['frames']:
        p = EV / (rec['name'] + '.rgb565')
        if not p.exists():
            frames.append(dict(name=rec['name'], error='missing file')); continue
        buf = p.read_bytes()
        img = decode(buf)
        lum = img @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        edges, bars = find_bars(img)
        bbox, colored = color_bbox(img)
        e = dict(name=rec['name'], cam=rec['cam'], bank=rec['bank'], frame=rec['frame'],
                 phase=rec.get('phase', ''), addr=rec['addr'], bytes=len(buf),
                 crc32=zlib.crc32(buf) & 0xffffffff,
                 luma_mean=round(float(lum.mean()), 2), luma_std=round(float(lum.std()), 2),
                 nonblack_frac=round(float((lum > 16).mean()), 4),
                 tag_before=rec['tag_before'], tag_after=rec['tag_after'],
                 tag_advanced=rec['tag_before'] != rec['tag_after'],
                 bar_edges=edges, n_bars=len(bars), bars=bars,
                 testpat_like=testpat_like(edges, bars, img),
                 color_bbox=bbox, colored_px=colored, uniform=bool(lum.std() < 1.0))
        frames.append(e)
        cache[e['name']] = (img, e)

    # distinctness between cameras within the same phase + frame index
    distinct = []
    for phase in sorted(set(e.get('phase') for e in frames if 'error' not in e)):
        for f in (0, 1):
            imgs = {}
            for cam in (1, 2, 3, 4):
                for n, (im, e) in cache.items():
                    if e['phase'] == phase and e['cam'] == cam and e['frame'] == f and e['bank'] == 0:
                        imgs[cam] = im
            for i in range(1, 5):
                for j in range(i + 1, 5):
                    if i in imgs and j in imgs:
                        mad = float(np.abs(imgs[i].astype(np.int16) - imgs[j].astype(np.int16)).mean())
                        distinct.append(dict(phase=phase, frame=f, pair='cam%d/cam%d' % (i, j),
                                             mad=round(mad, 3), distinct=bool(mad > 2.0)))

    # phase verdicts
    verdicts = []
    for phase, bar_cam, clean_cam in (('testpat4', 4, 3), ('testpat3', 3, 4)):
        b = [e for e in frames if e.get('phase') == phase and e['cam'] == bar_cam and 'error' not in e]
        c = [e for e in frames if e.get('phase') == phase and e['cam'] == clean_cam and 'error' not in e]
        if b and c:
            ok = all(e['testpat_like'] for e in b) and not any(e['testpat_like'] for e in c)
            verdicts.append(dict(phase=phase, bars_cam=bar_cam, bars_seen=all(e['testpat_like'] for e in b),
                                 clean_cam=clean_cam, clean_seen=any(e['testpat_like'] for e in c),
                                 pass_=bool(ok)))
    report = dict(frames=frames, distinctness=distinct, verdicts=verdicts, rates=cap.get('rates'))
    (EV / 'analysis.json').write_text(json.dumps(report, indent=2))

    if regs:
        print('=== register summary ===')
        for cam in range(4):
            s, e = regs[0]['cams'][cam], regs[-1]['cams'][cam]
            dt = regs[-1]['t'] - regs[0]['t']
            print('CAM%d success/s=%.2f offered_px=%s faults=%s CDC=%s' % (
                cam + 1, ((e['0xf0'] - s['0xf0']) & 0xffffffff) / dt,
                sorted(set(r['cams'][cam]['0x30'] for r in regs)),
                sorted(set(hex(r['cams'][cam]['0x0']) for r in regs)),
                {k: sorted(set(r['cdc'][cam][k] for r in regs)) for k in ('input', 'output', 'drop')}))

    print('=== frames ===')
    for e in frames:
        if 'error' in e:
            print('%-26s ERROR %s' % (e['name'], e['error'])); continue
        print('%-26s cam%d b%d f%d bytes=%d crc=%08x luma=%.1f/%.1f nonblack=%.3f '
              'tag_adv=%s nbars=%d testpat=%s bbox=%s uniform=%s' % (
                  e['name'], e['cam'], e['bank'], e['frame'], e['bytes'], e['crc32'],
                  e['luma_mean'], e['luma_std'], e['nonblack_frac'], e['tag_advanced'],
                  e['n_bars'], e['testpat_like'], e['color_bbox'], e['uniform']))

    print('=== cross-camera distinctness ===')
    bad = [d for d in distinct if not d['distinct']]
    for d in distinct:
        print('  %-9s f%d %s MAD=%.3f distinct=%s' % (d['phase'], d['frame'], d['pair'], d['mad'], d['distinct']))
    print('=== phase verdicts ===')
    for v in verdicts:
        print('  %-9s bars_on_cam%d=%s clean_on_cam%d=%s -> %s' % (
            v['phase'], v['bars_cam'], v['bars_seen'], v['clean_cam'], v['clean_seen'],
            'PASS' if v['pass_'] else 'FAIL'))
    print('ANALYZE_DONE ->', EV / 'analysis.json')
    if bad:
        print('WARNING: %d camera pair(s) not distinct' % len(bad))


if __name__ == '__main__':
    main()
