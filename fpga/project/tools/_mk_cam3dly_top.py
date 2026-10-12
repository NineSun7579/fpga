# -*- coding: utf-8 -*-
"""Top-file only: route the per-camera runtime IODELAY step (CRLF-aware)."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TOP = r"C:\Users\NineSun\Desktop\ov56401\project\source\ov5640\ov5640_top.v"

data = open(TOP, "rb").read()
pairs = [
    (
        "wire [7 : 0] cam_data_dly;\r\n",
        "wire [7 : 0] cam_data_dly;\r\n"
        "    // [CAM3DLY 2026-09-27] runtime DVP sampling delay (from ov5640_reg).\r\n"
        "    wire [7 : 0] reg_dly_step;\r\n",
        1,
    ),
    ('.DELAY_STEP_SEL("PARAMETER"),', '.DELAY_STEP_SEL("PORT"),', 3),
    (".DELAY_STEP (8'b0)", ".DELAY_STEP (reg_dly_step)", 3),
    (
        ".cam_en                (cam_en       ),\r\n",
        ".cam_en                (cam_en       ),\r\n"
        "        .dly_step              (reg_dly_step ),\r\n",
        1,
    ),
]
for old, new, cnt in pairs:
    ob, nb = old.encode("latin1"), new.encode("latin1")
    n = data.count(ob)
    assert n == cnt, "count %d != %d for %r" % (n, cnt, old[:60])
    data = data.replace(ob, nb)
open(TOP, "wb").write(data)
print("edited ov5640_top.v")
