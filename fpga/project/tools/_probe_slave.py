import re
b=open(r"source\top.v","rb").read().decode("gbk","replace").splitlines()
# map slave port -> signal prefix
for sp in ["s00","s01","s02","s03","s04","s05","s06"]:
    pref=set()
    for l in b:
        m=re.search(r"\.%s_axi_awvalid\s*\(\s*([A-Za-z0-9_]+)\s*\)"%sp, l)
        if m: pref.add(m.group(1))
    print("%s awvalid sources: %s"%(sp, sorted(pref)))
print()
print("### comments marking slave ports:")
for i,l in enumerate(b):
    if re.search(r"S0[0-6].*(camera|PCIe|host|preprocess|KF|DMA|npu|write|read)|\[.*\].*S0[0-6]", l) and len(l.strip())<130:
        print("%5d %s"%(i+1,l.strip()))
print()
print("### PCIe lanes:")
for i,l in enumerate(b):
    if re.search(r"2LANE|1LANE|GTP_HSST|x1|x2|LANE", l) and len(l.strip())<140:
        print("%5d %s"%(i+1,l.strip()))
