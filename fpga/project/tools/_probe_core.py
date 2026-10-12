import os, re, glob
print("### ov5640_clk IP files:")
for f in sorted(glob.glob("ipcore/ov5640_clk/*")):
    print("   ", f, (os.path.getsize(f) if os.path.isfile(f) else ""))
print()
print("### core_clk / video_clk / clk_150m assignments in top.v:")
b=open(r"source\top.v","rb").read().decode("gbk","replace").splitlines()
for i,l in enumerate(b):
    if re.search(r"core_clk\s*=|wire\s+core_clk|video_clk\s*=|clk_150m\s*=|assign\s+core_clk|ov5640_clk\s+", l):
        print("%5d %s"%(i+1,l.strip()[:120]))
print()
print("### ov5640_clk instance ports (top.v 900-975):")
for i in range(899,975):
    print("%5d %s"%(i+1,b[i].strip()[:120]))
