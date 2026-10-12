# -*- coding: utf-8 -*-
"""_diff.py <a> <b> [ctx] : GBK-safe unified diff of two RTL files."""
import io
import os
import sys
import difflib

os.chdir(r'C:\Users\NineSun\Desktop\ov56401\project')
a, b = sys.argv[1], sys.argv[2]
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 2


def lines(p):
    d = open(p, 'rb').read()
    return [l.decode('gbk', 'replace').rstrip('\r') for l in d.split(b'\n')]


A, B = lines(a), lines(b)
print('--- %s  (%d lines)' % (a, len(A)))
print('+++ %s  (%d lines)' % (b, len(B)))
n = 0
for line in difflib.unified_diff(A, B, lineterm='', n=ctx):
    print(line)
    n += 1
    if n > 400:
        print('... (truncated)')
        break
if n == 0:
    print('(identical)')
