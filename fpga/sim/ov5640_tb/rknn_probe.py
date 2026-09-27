#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe an RKNN model with rknn-toolkit2 x86 simulator (run inside WSL)."""
import sys
import numpy as np

path = sys.argv[1] if len(sys.argv) > 1 else \
    "/mnt/c/Users/NineSun/Desktop/ov56401/project/usb_deploy/detview/models/vehicles_1cls_640_std.rknn"
img_path = sys.argv[2] if len(sys.argv) > 2 else \
    "/mnt/c/Users/NineSun/Desktop/ov56401/project/migration/RK3568_PG100H-release/VS_C++/Yolov5/img/000001.jpg"

from rknn.api import RKNN
import cv2

print("load:", path)
r = RKNN(verbose=False)
ret = r.load_rknn(path)
print("load_rknn ret:", ret)
ret = r.init_runtime()
print("init_runtime ret:", ret)

img = cv2.imread(img_path)
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
h, w = img.shape[:2]
s = min(640.0 / w, 640.0 / h)
nw, nh = int(round(w * s)), int(round(h * s))
rs = cv2.resize(img, (nw, nh))
canvas = np.zeros((640, 640, 3), np.uint8)
ox, oy = (640 - nw) // 2, (640 - nh) // 2
canvas[oy:oy + nh, ox:ox + nw] = rs
print("input canvas", canvas.shape, canvas.dtype)

outs = r.inference(inputs=[canvas])
for i, o in enumerate(outs):
    o = np.asarray(o)
    print("out[%d] shape=%s dtype=%s min=%.4f max=%.4f" %
          (i, o.shape, o.dtype, float(o.min()), float(o.max())))
