import os, re, glob
def show(title, pats, files, enc="gbk", maxhit=40):
    print("="*70); print(title)
    n=0
    for f in files:
        try:
            b=open(f,"rb").read().decode(enc,"replace").splitlines()
        except Exception as e:
            continue
        for i,l in enumerate(b):
            for p in pats:
                if re.search(p,l):
                    print("%-46s %5d %s" % (f.replace("\\","/"), i+1, l.strip()[:120]))
                    n+=1; break
            if n>=maxhit: return
print("### .fdc constraint files:")
for f in glob.glob("source/constraints/*.fdc"): print("   ", f)
show("### create_clock / period in .fdc", [r"create_clock", r"-period", r"FREQ", r"clk"], glob.glob("source/constraints/*.fdc"))
show("### PLL / freq in ipcore (ddr3, pll)", [r"freq", r"FREQ", r"clkout", r"MHz", r"MHZ"], 
     glob.glob("ipcore/ddr3/**/*.v",recursive=True)+glob.glob("ipcore/*pll*/**/*.v",recursive=True)+glob.glob("ipcore/*pll*/*.v"), maxhit=60)
show("### CMOS display geometry", [r"H_CMOS_DISP", r"V_CMOS_DISP", r"base_addr", r"BASE_ADDR"], ["source/ov5640/ov5640_top.v"], maxhit=20)
