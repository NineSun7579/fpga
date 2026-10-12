import re
p = "session-ses_f422.md"
txt = open(p, "rb").read().decode("utf-8", "replace")
lines = txt.splitlines()
print("total lines", len(lines))
pats = [r"v2\.ko", r"new\.ko", r"old\.ko", r"最新驱动", r"pango_pci_driver\.(ko|new|v2|old)", r"insmod"]
hits = [(i+1, l.strip()) for i, l in enumerate(lines) if any(re.search(x, l) for x in pats)]
print("hits", len(hits))
for i, l in hits[-45:]:
    print("%6d %s" % (i, l[:150]))
