# -*- coding: utf-8 -*-
"""Dump cam3's *active* pin table and check for pin (LOC) conflicts across all .fdc."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\NineSun\Desktop\ov56401\project\source\constraints"

net_loc = {}   # loc -> set of nets (active lines only)
net_loc_all = {}
for f in sorted(os.listdir(D)):
    if not f.endswith(".fdc"):
        continue
    for ln, line in enumerate(open(os.path.join(D, f), "rb").read().decode("gbk", "ignore").splitlines(), 1):
        s = line.strip()
        active = not (s.startswith("#") or s.startswith("//"))
        m = re.search(r"\{([pn]):([^}]+)\}\s*\{PAP_IO_LOC\}\s*\{([^}]+)\}", s)
        if not m:
            continue
        kind, net, loc = m.group(1), m.group(2), m.group(3)
        if kind != "p":
            continue
        net_loc_all.setdefault(loc, set()).add((net, f, ln))
        if active:
            net_loc.setdefault(loc, set()).add((net, f, ln))

CAM3 = ["cmos3_pclk", "cmos3_vsync", "cmos3_href", "cmos3_rst_n", "cmos3_scl", "cmos3_sda"] + \
       ["cmos3_data[%d]" % i for i in range(8)]

loc_of = {}
for loc, items in net_loc.items():
    for net, f, ln in items:
        if net in CAM3:
            loc_of[net] = (loc, f, ln)

print("=== cam3 ACTIVE pin table (source/constraints) ===")
for net in CAM3:
    if net in loc_of:
        loc, f, ln = loc_of[net]
        print("  %-16s -> %-6s   (%s:%d)" % (net, loc, f, ln))
    else:
        print("  %-16s ->  ** NOT DEFINED (active) **" % net)

print()
print("=== duplicate LOC usage (same package pin, multiple active nets) ===")
dups = 0
for loc, items in sorted(net_loc.items()):
    if len(items) > 1:
        dups += 1
        print("  %-6s : %s" % (loc, ", ".join("%s(%s:%d)" % it for it in sorted(items))))
if not dups:
    print("  none - every active pin location is used once")

print()
print("=== are cam3 pins also listed (commented) anywhere else? ===")
for net in CAM3:
    loc, f, ln = loc_of.get(net, (None, None, None))
    hits = [(n, ff, l2) for l2, its in net_loc_all.items() for (n, ff, l2x) in its
            for n2 in [n] if n == net]
    # simpler: list all occurrences of this net
    occ = []
    for loc2, items in net_loc_all.items():
        for n, ff, l2 in items:
            if n == net:
                occ.append("%s@%s:%d" % (loc2, ff, l2))
    print("  %-16s : %s" % (net, ", ".join(sorted(set(occ)))))
