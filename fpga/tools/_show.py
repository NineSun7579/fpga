# -*- coding: utf-8 -*-
"""show <file> <pattern> [ctx] : print matching lines with context (GBK-safe)."""
import io
import os
import sys

os.chdir(r'C:\Users\NineSun\Desktop\ov56401\project')
path, pat = sys.argv[1], sys.argv[2].encode()
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 6
d = open(path, 'rb').read()
lines = d.split(b'\n')
hits = [i for i, l in enumerate(lines) if pat in l]
shown = set()
for i in hits:
    a = max(0, i - ctx)
    b = min(len(lines), i + ctx + 1)
    for j in range(a, b):
        shown.add(j)
prev = -2
for j in sorted(shown):
    if j != prev + 1:
        print('   ...')
    print('%4d| %s' % (j + 1, lines[j].decode('gbk', 'replace').rstrip()))
    prev = j
