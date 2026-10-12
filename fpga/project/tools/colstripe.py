import struct, sys

def ppm(path):
    d = open(path, 'rb').read()
    parts, i = [], 0
    while len(parts) < 4:
        while d[i:i+1].isspace(): i += 1
        if d[i:i+1] == b'#':
            while d[i:i+1] != b'\n': i += 1
            continue
        j = i
        while not d[j:j+1].isspace(): j += 1
        parts.append(d[i:j]); i = j
    i += 1
    w, h = int(parts[1]), int(parts[2])
    return w, h, d[i:i + w*h*3]

for name in ('/tmp/cam1_kf.ppm', '/tmp/cam2_raw.ppm'):
    try:
        w, h, px = ppm(name)
    except Exception as e:
        print(name, 'ERR', e); continue
    rows = min(h, 480)
    gcol = [0.0]*w
    for x in range(w):
        s = 0
        for y in range(0, rows, 2):
            s += px[(y*w + x)*3 + 1]
        gcol[x] = s
    n = len(gcol)
    m = sum(gcol)/n
    hp = [gcol[x] - (sum(gcol[max(0,x-4):x+5])/len(gcol[max(0,x-4):x+5])) for x in range(n)]
    mu = sum(hp)/n
    var = sum((v-mu)**2 for v in hp)/n
    rms = var ** 0.5
    lags = []
    for L in (2,3,4,5,6,7,8):
        num = sum((hp[x]-mu)*(hp[x+L]-mu) for x in range(n-L))
        den = sum((v-mu)**2 for v in hp)
        lags.append((L, num/den if den else 0))
    print('%s %dx%d GcolHP-RMS=%.3f lags=%s' % (
        name.split('/')[-1], w, h, rms,
        ' '.join('L%d:%+.3f' % (l, v) for l, v in lags)))
print('ANALYSIS_DONE')
