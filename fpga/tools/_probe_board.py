import os, re, glob
def dump(f, n=70):
    print("="*72); print(f)
    if not os.path.exists(f):
        print("  MISSING"); return
    try: b=open(f,"rb").read().decode("utf-8","replace").splitlines()
    except Exception as e: print("  ERR", e); return
    for i,l in enumerate(b[:n]): print("%4d %s"%(i+1,l[:150]))
    if len(b)>n: print("  ... (%d more lines)"%(len(b)-n))
for f in ["tools/sshx.py","tools/fetch.py","tools/burn_now.py","tools/board_gui_shot.sh","tools/board_dualcap.py"]:
    dump(f, 70)
print("="*72); print("### IPs found in tools/ and DOC/:")
for f in sorted(glob.glob("tools/*")+glob.glob("DOC/*")):
    if os.path.isfile(f):
        try: b=open(f,"rb").read().decode("utf-8","replace")
        except: continue
        for m in sorted(set(re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", b))):
            print("   %-42s %s"%(f, m))
