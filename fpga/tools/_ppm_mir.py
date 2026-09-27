import math

P = '/root/ov5640/detview_selftest.ppm'
data = open(P, 'rb').read()
i = 0
nl = 0
while nl < 3:
    if data[i] == 10:
        nl += 1
    i += 1
px = data[i:]
W = H = 640


def gray(x, y):
    o = (y * W + x) * 3
    return (px[o] * 299 + px[o + 1] * 587 + px[o + 2] * 114) // 1000


def mir(x):
    return (x & ~7) | (7 - (x & 7))


# ---- global mirror test on high-frequency detail ----
# subtract a 1D local mean (window 16) so smooth gradients cannot fake symmetry
for name, y0, y1 in (('cam1 frame mid', 100, 540),):
    sm = 0
    sa = 0
    n = 0
    for y in range(y0, y1, 2):
        g = [gray(x, y) for x in range(W)]
        for x in range(8, W - 8):
            sm += abs(g[mir(x)] - g[x])
            sa += abs(g[x + 1] - g[x]) if x + 1 < W else 0
            n += 1
    print('%-16s mean|g[mir(x)]-g[x]| = %6.3f   mean|g[x+1]-g[x]| = %6.3f'
          % (name, sm / n, sa / n))

# ---- per-word mirror correlation (fwd vs rev) ----
cr = 0.0
cf = 0.0
m = 0
for y in range(100, 540, 2):
    g = [gray(x, y) for x in range(W)]
    for k in range(0, W // 8):
        a = g[8 * k:8 * k + 4]
        b = g[8 * k + 4:8 * k + 8]
        br = b[::-1]
        ma = sum(a) / 4.0
        mb = sum(b) / 4.0
        da = sum((v - ma) ** 2 for v in a)
        db = sum((v - mb) ** 2 for v in b)
        if da < 4 or db < 4:
            continue
        cr += sum((a[j] - ma) * (br[j] - mb) for j in range(4)) / math.sqrt(da * db)
        cf += sum((a[j] - ma) * (b[j] - mb) for j in range(4)) / math.sqrt(da * db)
        m += 1
print('words with detail: %d' % m)
print('mean corr(a, reverse(b)) = %+.4f   <-- mirror if high' % (cr / m))
print('mean corr(a,         b ) = %+.4f' % (cf / m))

# ---- dump 16 consecutive words with mirror index ----
y = 320
print('--- row 320, x=32..95 (word index / value) ---')
for k in range(4, 12):
    vals = [gray(x, y) for x in range(8 * k, 8 * k + 8)]
    pair = ['%d-%d' % (vals[j], vals[7 - j]) for j in range(4)]
    print('  word %2d : %s   mirror-pairs(L,R): %s'
          % (k, ' '.join('%3d' % v for v in vals), '  '.join(pair)))
print('MIR_DONE')
