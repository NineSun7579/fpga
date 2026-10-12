import re, glob, os
# resource summary
for f in glob.glob("project_kf/synthesize/*")+glob.glob("project_kf/*.log")+glob.glob("project_kf/place_route/*.txt"):
    if not os.path.isfile(f): continue
    try: b=open(f,"rb").read().decode("utf-8","replace").splitlines()
    except: continue
    hits=[(i+1,l.strip()) for i,l in enumerate(b) if re.search(r"DRM|DRAM|BRAM|LUT|Register|Slice|Utiliz|Resource", l) and len(l.strip())<120]
    if 2<len(hits)<40:
        print("---",f)
        for i,l in hits[:22]: print("   %5d %s"%(i,l))
