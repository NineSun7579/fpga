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


def rgb(x, y):
    o = (y * W + x) * 3
    return px[o], px[o + 1], px[o + 2]


for y in (240, 320):
    r = [rgb(x, y)[0] for x in range(32, 64)]
    g = [rgb(x, y)[1] for x in range(32, 64)]
    b = [rgb(x, y)[2] for x in range(32, 64)]
    print('y=%d R[32..63]:' % y, ' '.join('%3d' % v for v in r))
    print('y=%d G[32..63]:' % y, ' '.join('%3d' % v for v in g))
    print('y=%d B[32..63]:' % y, ' '.join('%3d' % v for v in b))
    print()

print('--- 2D G / 4 map, rows 300..311, x=36..67 ---')
for y in range(300, 312):
    row = []
    for x in range(36, 68):
        row.append('%2d' % (rgb(x, y)[1] >> 2))
    print('y=%3d' % y, ' '.join(row))

print('--- 2D R / 4 map, rows 300..311, x=36..67 ---')
for y in range(300, 312):
    row = []
    for x in range(36, 68):
        row.append('%2d' % (rgb(x, y)[0] >> 2))
    print('y=%3d' % y, ' '.join(row))

print('RGB_DUMP_DONE')
