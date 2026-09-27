import re
b=open(r"source\top.v","rb").read().decode("gbk","replace").splitlines()
pats=[r"axi_crossbar",r"ddr_w_arb",r"ddr_w_",r"CONNECT_READ",r"CONNECT_WRITE",r"M\d\d_CONNECT",r"S0\d_",r"\.s0\d_",r"_s0\d_",r"\.m0\d_",r"\.num_",r"slave|master",r"arb"]
n=0
for i,l in enumerate(b):
    for p in pats:
        if re.search(p,l):
            print("%5d %s"%(i+1,l.strip()[:130])); n+=1; break
    if n>150: break
