import os, re
pats=[r"COM9", r"1500000", r"serial\.Serial", r"pyserial", r"serial\.", r"baudrate"]
for dp,dn,fn in os.walk("."):
    if any(x in dp for x in ("\\.git","ipcore","_attic\\bak")): continue
    for f in fn:
        if not f.endswith((".py",".sh",".md",".ps1")): continue
        p=os.path.join(dp,f)
        try: raw=open(p,"rb").read()
        except: continue
        txt=None
        for enc in ("utf-8","gbk"):
            try: txt=raw.decode(enc); break
            except: pass
        if txt is None: continue
        hits=[(i+1,l.strip()) for i,l in enumerate(txt.splitlines()) if any(re.search(x,l) for x in pats)]
        if hits:
            print("--- %s (%d)"%(p,len(hits)))
            for i,l in hits[:5]: print("   %5d %s"%(i,l[:120]))
