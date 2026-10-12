import os, re, hashlib
print("=== all .ko (md5 size mtime path) ===")
for dp, dn, fn in os.walk('.'):
    if 'ipcore' in dp or '.git' in dp: continue
    for f in fn:
        if f.endswith('.ko'):
            p = os.path.join(dp, f)
            try: b = open(p, 'rb').read()
            except Exception: continue
            print('  %s %8d %s  %s' % (hashlib.md5(b).hexdigest(), len(b), __import__('time').strftime('%m-%d %H:%M', __import__('time').localtime(os.path.getmtime(p))), p))
print("=== references to driver ko / latest driver ===")
pats = [r'v2\.ko', r'new\.ko', r'max[14]\.ko', r'pango_pci_driver', r'最新驱动']
for dp, dn, fn in os.walk('.'):
    if 'ipcore' in dp or '.git' in dp: continue
    for f in fn:
        if not f.endswith(('.py', '.md', '.sh', '.txt', '.ps1', '.log', '.c', '.h')): continue
        p = os.path.join(dp, f)
        try:
            if os.path.getsize(p) > 2_000_000: continue
            raw = open(p, 'rb').read()
        except Exception: continue
        txt = None
        for enc in ('utf-8', 'gbk'):
            try: txt = raw.decode(enc); break
            except Exception: pass
        if txt is None: continue
        hits = [(i + 1, l.strip()) for i, l in enumerate(txt.splitlines()) if any(re.search(x, l) for x in pats)]
        if hits:
            print('--- %s (%d)' % (p, len(hits)))
            for i, l in hits[:4]: print('   %5d %s' % (i, l[:120]))
