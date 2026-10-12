import os
for root,dirs,files in os.walk("host"):
    d=root.count(os.sep)
    if d>2: dirs[:]=[]; continue
    print(root+"/")
    for f in files: print("   ", f, os.path.getsize(os.path.join(root,f)))
