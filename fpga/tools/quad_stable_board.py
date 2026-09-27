import sys, time

# [CAM4 2026-09-27] Sustained-output probe: samples every camera's DVP/CDC
# counters for ~60 s using register reads only (no DMA, no frame grabs), and
# reports monotonic progress + drop=0. Complements the frame-level acceptance.

sys.path.insert(0, '/tmp')
import cam3_i2c_pt as m

CAMS = [
    (0x20000000, 1),
    (0x20000200, 2),
    (0x20000400, 3),
    (0x20000600, 4),
]

d = m.PciDriver()
r = d.read32

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DT = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
rows = []
for i in range(N):
    line = []
    for base, idx in CAMS:
        line.append((idx, r(base + 0x10), r(base + 0x20), r(base + 0x30),
                     r(base + 0xf0), r(base + 0x190), r(base + 0x1a0), r(base + 0x1b0)))
    rows.append(line)
    print('t=%5.1fs ' % (i * DT) + ' | '.join(
        'C%d pclk=%d vs=%d w=%d fr=%d cdc=%d/%d' % (x[0], x[1], x[2], x[3], x[4], x[5], x[6]) for x in line),
        flush=True)
    time.sleep(DT)

print('--- summary over %.0fs ---' % (N * DT))
for j, (base, idx) in enumerate(CAMS):
    p0, p1 = rows[0][j][1], rows[-1][j][1]
    v0, v1 = rows[0][j][2], rows[-1][j][2]
    f0, f1 = rows[0][j][4], rows[-1][j][4]
    drops = [row[j][7] for row in rows]
    seqs = [row[j][5] for row in rows]
    words = rows[-1][j][3]
    print('C%d dPCLK=%-12d dVS=%-6d dFRAMES=%-6d drop max=%d words=%d seq_adv=%s' % (
        idx, p1 - p0, v1 - v0, f1 - f0, max(drops), words, seqs[-1] != seqs[0]))
