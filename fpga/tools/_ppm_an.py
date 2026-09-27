import collections

P = '/root/ov5640/detview_selftest.ppm'
data = open(P, 'rb').read()

i = 0
nl = 0
while nl < 3:
    if data[i] == 10:
        nl += 1
    i += 1
print('hdr:', data[:i].decode('ascii', 'replace').replace('\n', '|'))
px = data[i:]
W = H = 640
print('payload bytes:', len(px), ' expect', W * H * 3)


def gray(o):
    return (px[o] * 299 + px[o + 1] * 587 + px[o + 2] * 114) // 1000


# ---- locate the letterboxed frame region ----
rm = []
for y in range(0, H, 20):
    o = y * W * 3
    s = 0
    for x in range(0, W, 8):
        s += gray(o + 3 * x)
    rm.append((y, s // 80))
print('row means (y,mean):', rm)

# rows with content
ys = [y for y in range(H) if True]
y0, y1 = 80, 560
print('assume frame rows %d..%d' % (y0, y1))

# ---- raw waveform of a few frame rows (lossless source pixels) ----
for y in (200, 240, 241, 320):
    o = y * W * 3
    vals = [gray(o + 3 * x) for x in range(64)]
    print('row %3d :' % y, ' '.join('%3d' % v for v in vals))

# ---- mean |d| vs shift, over frame rows ----
print('--- mean|G(x+p)-G(x)| ---')
for pp in range(1, 17):
    s = 0
    c = 0
    for y in range(y0, y1, 3):
        o = y * W * 3
        g = [gray(o + 3 * x) for x in range(W)]
        for x in range(0, W - pp):
            s += abs(g[x + pp] - g[x])
            c += 1
    print('  p=%2d : %7.4f' % (pp, s / c))

# ---- column-mean profile autocorrelation ----
cm = [0.0] * W
n = 0
for y in range(y0, y1):
    o = y * W * 3
    for x in range(W):
        cm[x] += gray(o + 3 * x)
    n += 1
cm = [v / n for v in cm]
mu = sum(cm) / W
cm = [v - mu for v in cm]
var = sum(v * v for v in cm)
print('--- column-profile autocorr ---')
for pp in range(1, 25):
    s = sum(cm[x] * cm[x + pp] for x in range(W - pp))
    print('  lag %2d : %+.4f' % (pp, s / var))

# ---- per-row best lag (2..12) ----
hist = collections.Counter()
for y in range(y0, y1, 2):
    o = y * W * 3
    g = [gray(o + 3 * x) for x in range(W)]
    best = 0
    bv = 1e18
    for pp in range(2, 13):
        v = sum(abs(g[x + pp] - g[x]) for x in range(W - pp)) / (W - pp)
        if v < bv:
            bv = v
            best = pp
    hist[best] += 1
print('--- per-row best lag histogram (2..12) ---')
print(' ', dict(sorted(hist.items())))
print('--- column profile [0:80] ---')
print(' ', ' '.join('%5.1f' % v for v in cm[:80]))
print('AN_PPM_DONE')
