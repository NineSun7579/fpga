import os, re, glob
print("### ipcore/ddr3 listing (top 40):")
p="ipcore/ddr3"
for root,dirs,files in os.walk(p):
    for f in files[:0]: pass
    for f in sorted(files):
        print("   ", os.path.join(root,f).replace("\\","/"))
