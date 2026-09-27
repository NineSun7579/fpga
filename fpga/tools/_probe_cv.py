import re
p = "host/camview/main.cpp"
txt = open(p, "rb").read().decode("utf-8", "replace")
lines = txt.splitlines()
print("lines:", len(lines))
pats = [r"0x0080|0x00C0|0x00A0|0x00E0", r"CAM1|CAM2|cam1|cam2", r"sharp|ledger|median|filter|blur|Sharpen",
        r"scaled|Smooth|Fast|drawImage|QImage|Formats", r"panel|left|right|half|每|左|右",
        r"KF|kf_", r"DDR|ddr_|addr", r"Qual|IPLL|E1|E2|C2"]
for i, l in enumerate(lines):
    s = l.strip()
    if any(re.search(x, s) for x in pats):
        print("%5d %s" % (i+1, s[:150]))
