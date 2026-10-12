import os, re
roots=["tools","DOC","sim","_attic","project","source"]
pats=[r"debug\s*口",r"串口",r"COM\d+",r"ttyUSB",r"ttyS[0-9]",r"115200",r"serial",r"minicom",r"picocom",r"screen\s+/dev",r"putty",r"cdt_js",r"cdt_cfg",r"65425",r"console"]
seen=set()
for root in roots:
    for dp,dn,fn in os.walk(root):
        for f in fn:
            p=os.path.join(dp,f)
            if p in seen: continue
            seen.add(p)
            if os.path.getsize(p)>3_000_000: continue
            try: raw=open(p,"rb").read()
            except: continue
            for enc in ("gbk","utf-8"):
                try: txt=raw.decode(enc); break
                except: txt=None
            if txt is None: continue
            onl=[l.strip() for l in txt.splitlines() if any(re.search(x,l,re.I) for x in pats)]
            if onl:
                print("---",p,"(%d)"%len(onl))
                for l in onl[:6]: print("     ",l[:130])
