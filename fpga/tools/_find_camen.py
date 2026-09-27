# -*- coding: utf-8 -*-
"""Byte-level search (GBK-safe) for CAM_EN semantics and any 48 MHz references."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"

PATTERNS = [
    rb"cam_en",
    rb"cam3_en",
    rb"CAM_EN",
    rb"0x40",
    rb"3036",
    rb"\b48m\b",
    rb"48_?MHz",
    rb"48 MHz",
]

SKIP_DIRS = {"．", "compile", "synthesize", "device_map", "place_route",
             "generate_bitstream", "generate_netlist", "sim", "__pycache__"}


def walk(base, exts):
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in exts:
                yield os.path.join(dp, fn)


def main():
    targets = []
    targets += [(os.path.join(ROOT, "source"), {".v", ".sv", ".vh"})]
    targets += [(os.path.join(ROOT, "DOC"), {".md", ".txt"})]
    for base, exts in targets:
        for path in walk(base, exts):
            try:
                data = open(path, "rb").read()
            except OSError:
                continue
            lines = data.split(b"\n")
            for i, ln in enumerate(lines, 1):
                for pat in PATTERNS:
                    if re.search(pat, ln, re.IGNORECASE):
                        rel = os.path.relpath(path, ROOT)
                        txt = ln.decode("gbk", "replace").strip()
                        print("%s:%d: %s" % (rel, i, txt[:160]))
                        break


main()
