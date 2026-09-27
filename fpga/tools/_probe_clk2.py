import re
b=open(r"source\top.v","rb").read().decode("gbk","replace").splitlines()
print("### axi_clk / video_clk / core_clk definitions:")
for i,l in enumerate(b):
    if re.search(r"(assign\s+)?axi_clk\s*=|wire\s+axi_clk|video_clk\s*=|assign\s+clk_150|crossbar.*clk|\.clk\s*\(\s*axi_clk|\.clk\s*\(.*ddrphy", l):
        print("%5d %s"%(i+1,l.strip()[:120]))
print()
print("### ddr_w_arb instantiation region (top.v 405-427):")
for i in range(404,427):
    print("%5d %s"%(i+1,b[i].strip()[:130]))
print()
print("### who drives the 2 write masters into ddr_w_arb (search s_awid source):")
for i,l in enumerate(b):
    if re.search(r"arb_s_awid|w_arb.*00_axi|ddr_w_arb|m0_awid|m1_awid|\.s0_axi|\.s1_axi", l):
        print("%5d %s"%(i+1,l.strip()[:130]))
