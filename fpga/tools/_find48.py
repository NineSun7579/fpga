# -*- coding: utf-8 -*-
"""Search the project for the historical 48 MHz config (docs + backups)."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\Users\NineSun\Desktop\ov56401\project"
PAT = re.compile(rb"48\s?M|tearfree|tear.?free|0x3036|3036|PLL|pll_mult|48MHz", re.IGNORECASE)
SKIP = {"compile", "synthesize", "device_map", "place_route", "generate_bitstream",
        "generate_netlist", ".git", "__pycache__", "sim", "ipcore", "source"}

for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in SKIP]
    depth = dp[len(ROOT):].count(os.sep)
    if depth > 3:
        continue
    for f in fn:
        if os.path.splitext(f)[1].lower() not in (".md", ".txt", ".tcl", ".log", ".py"):
            continue
        p = os.path.join(dp, f)
        try:
            lines = open(p, "rb").read().split(b"\n")
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if PAT.search(ln):
                rel = os.path.relpath(p, ROOT)
                print("%s:%d: %s" % (rel, i, ln.decode("gbk", "replace").strip()[:150]))
