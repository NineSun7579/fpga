# -*- coding: utf-8 -*-
"""Crop + upscale regions of the camview screenshot for close inspection."""
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = r"C:\Users\NineSun\Desktop\ov56401\project\cam3_now.png"
im = Image.open(SRC)
print("size", im.size)

# whole middle band (the three panels) upscaled
im.crop((0, 140, 1000, 430)).resize((2000, 580), Image.NEAREST).save(
    r"C:\Users\NineSun\Desktop\ov56401\project\_panels.png")

# cam3 panel only, upscaled 4x
im.crop((650, 140, 1000, 430)).resize((1400, 1160), Image.NEAREST).save(
    r"C:\Users\NineSun\Desktop\ov56401\project\_cam3.png")

# cam1 panel only, upscaled 4x
im.crop((0, 140, 315, 430)).resize((1260, 1160), Image.NEAREST).save(
    r"C:\Users\NineSun\Desktop\ov56401\project\_cam1.png")

# cam2 panel only, upscaled 4x
im.crop((318, 140, 645, 430)).resize((1308, 1160), Image.NEAREST).save(
    r"C:\Users\NineSun\Desktop\ov56401\project\_cam2.png")
print("saved crops")
