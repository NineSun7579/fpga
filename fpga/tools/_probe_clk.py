import os, re, glob
print("### ipcore/ top-level entries:")
for f in sorted(os.listdir("ipcore")):
    print("   ", f)
print()
print("### timing summary clock list (clocks + periods):")
for f in glob.glob("project_kf/place_route/*.txt")+glob.glob("project_kf/place_route/*.rpt"):
    try: b=open(f,"rb").read().decode("utf-8","replace").splitlines()
    except: continue
    hits=[(i+1,l.strip()) for i,l in enumerate(b) if re.search(r"Period|Frequency|MHz|ns\b|create_clock|Clock\s+Name|ddrphy|video_clk|pclk|core_clk|clk_150", l)]
    if hits:
        print("---", f)
        for i,l in hits[:40]: print("   %5d %s"%(i,l[:120]))
print()
print("### PLL / gpll config search:")
for f in glob.glob("ipcore/**/*", recursive=True):
    if os.path.isfile(f) and re.search(r"\.(v|txt|json|ini|xml|cfg|dat|prj)$", f):
        try: b=open(f,"rb").read().decode("utf-8","replace").splitlines()
        except: continue
        for i,l in enumerate(b):
            if re.search(r"CLKOUT|DIVCLK|CLKIN_FREQ|CLKFBOUT|MULT|DIVIDE|ddrphy_sysclk\s*=", l):
                print("%-52s %5d %s"%(f,i+1,l.strip()[:100]))
