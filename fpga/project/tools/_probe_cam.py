import os, re, glob
# 1) find OV5640 init/config tables
print("### ov5640 source files:")
for f in sorted(glob.glob("source/ov5640/**/*.v", recursive=True)):
    print("   ", f, os.path.getsize(f))
print()
print("### search for OV5640 reg table / fps markers:")
pats=[r"3035",r"3036",r"3037",r"fps",r"FPS",r"frame_rate",r"VTS",r"HTS",r"5048",r"reg.*<=",r"8'h30"]
for f in glob.glob("source/ov5640/**/*.v", recursive=True):
    try: b=open(f,"rb").read().decode("gbk","replace").splitlines()
    except: continue
    hits=[(i+1,l.strip()) for i,l in enumerate(b) if any(re.search(p,l) for p in pats)]
    if len(hits)>3:
        print("---", f, "(%d hits)"%len(hits))
        for i,l in hits[:12]: print("   %5d %s"%(i,l[:110]))
