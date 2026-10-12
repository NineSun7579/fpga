# -*- coding: utf-8 -*-
"""GBK-safe search for the DDR write-engine busy / timeout logic."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\NineSun\Desktop\ov56401\project\source"
PAT = re.compile(rb"engine_busy|watchdog|timeout|wdog|frame_done|wr_busy|write_busy|busy_cnt|wd_cnt",
                 re.IGNORECASE)
SKIP = {"compile", "synthesize", "device_map", "place_route"}

hits = 0
for dp, dn, fn in os.walk(BASE):
    dn[:] = [d for d in dn if d not in SKIP]
    for f in fn:
        if os.path.splitext(f)[1].lower() not in (".v", ".sv", ".vh"):
            continue
        p = os.path.join(dp, f)
        try:
            lines = open(p, "rb").read().split(b"\n")
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if PAT.search(ln):
                rel = os.path.relpath(p, os.path.dirname(BASE))
                print("%s:%d: %s" % (rel, i, ln.decode("gbk", "replace").strip()[:150]))
                hits += 1
print("HITS", hits)
