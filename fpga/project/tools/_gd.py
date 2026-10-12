# -*- coding: utf-8 -*-
import os
import re

os.chdir(r'C:\Users\NineSun\Desktop\ov56401\project')
d = open(r'source\top.v', 'rb').read()

for m in re.finditer(rb'ov5640_ddr\b', d):
    s = max(0, m.start() - 120)
    e = min(len(d), m.start() + 1600)
    print(d[s:e].decode('latin1'))
    print('=' * 70)
