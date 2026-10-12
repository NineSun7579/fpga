# -*- coding: utf-8 -*-
"""Convert the dumped cam3 PPMs to PNG so they can be viewed."""
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = r"C:\Users\NineSun\Desktop\ov56401\project\tp"
for nm in ("rc\\rc_bar_1", "rc\\rc_norm_1", "rc\\rc_norm_2", "rc\\rc_norm_3"):
    s = d + "\\" + nm + ".ppm"
    o = d + "\\" + nm.replace("\\", "_") + ".png"
    im = Image.open(s)
    im.resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST).save(o)
    print("wrote", o, im.size)
